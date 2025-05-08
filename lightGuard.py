import ctypes
import json
import os
import tkinter as tk
import re
import schedule
import subprocess
import sys
import winreg
import time
import keyboard
import threading
from pystray import Icon, MenuItem, Menu
from monitorcontrol import get_monitors
from PIL import Image, ImageDraw
from tkinter import messagebox
from datetime import datetime

# Manage settings with a JSON file
SETTINGS_FILE = os.path.expanduser("~\\AppData\\Local\\MonitorControl\\settings.json")

# Create the directory if it doesn't exist
os.makedirs(os.path.dirname(SETTINGS_FILE), exist_ok=True)

# Default settings
default_settings = {
    "window_x": 100,
    "window_y": 100,
    "day_brightness": 80,
    "night_brightness": 50,
    "day_contrast": 80,
    "night_contrast": 50,
    "day_start": "07:00",
    "day_end": "19:00",
    "night_start": "19:00",
    "night_end": "07:00",
    "day_shortcut": "Ctrl+Alt+D",
    "night_shortcut": "Ctrl+Alt+N"
}

# Functions to load/save settings
def load_settings():
    settings = default_settings.copy()

    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, "r") as file:
                user_settings = json.load(file)

                for key, default_value in default_settings.items():
                    if key in user_settings and isinstance(user_settings[key], type(default_value)):
                        settings[key] = user_settings[key]

        except (json.JSONDecodeError, IOError) as e:
            # Hidden root is required to start a tkinter window on non-starter systems
            hidden_root = tk.Tk()
            hidden_root.withdraw()
            messagebox.showwarning(
                title="Corrupted Settings File",
                message="The settings file (settings.json) could not be read.\nDefault settings have been loaded.",
                parent=hidden_root
            )
            save_settings(default_settings)  # Save default settings to the file
            hidden_root.destroy()

    save_settings(settings)
    return settings


def add_to_startup():
    """Uygulamayı Windows başlangıcına ekler"""
    key = winreg.HKEY_CURRENT_USER
    path = r"Software\Microsoft\Windows\CurrentVersion\Run"
    app_name = "LightGuard"
    exe_path = sys.executable  # Python scriptini doğrudan çalıştırmak için

    try:
        registry_key = winreg.OpenKey(key, path, 0, winreg.KEY_SET_VALUE)
        winreg.SetValueEx(registry_key, app_name, 0, winreg.REG_SZ, exe_path)
        winreg.CloseKey(registry_key)
        print("✅ LightGuard başarıyla başlangıca eklendi!")
    except Exception as e:
        print(f"❌ Başlangıca eklenirken hata oluştu: {e}")


# Save settings to JSON file
def save_settings(settings):
    with open(SETTINGS_FILE, "w") as file:
        json.dump(settings, file, indent=4)

# Function to close the settings window
def close_settings_window(root_settings):
    """Close the settings window."""
    root_settings.destroy()

# **Important:** Load settings at the beginning of the code
settings = load_settings()

# Function to change monitor brightness and contrast
def set_brightness_contrast(brightness, contrast):
    monitors = get_monitors()
    if monitors:
        with monitors[0] as monitor:
            monitor.set_luminance(brightness)
            monitor.set_contrast(contrast)
    else:
        print("ERROR: No monitor found.")

# Function to check if the current time is within a specified range
def is_time_in_range(start, end, now):
    """Supports cases where the range crosses midnight, such as night."""
    if start <= end:
        return start <= now < end
    else:  # e.g., 19:00 - 07:00
        return now >= start or now < end

# Function to apply current brightness and contrast settings based on time
def apply_current_brightness_contrast():
    try:
        now = datetime.now().time()
        day_start = datetime.strptime(settings["day_start"], "%H:%M").time()
        day_end = datetime.strptime(settings["day_end"], "%H:%M").time()

        if is_time_in_range(day_start, day_end, now):
            set_brightness_contrast(settings["day_brightness"], settings["day_contrast"])
        else:
            set_brightness_contrast(settings["night_brightness"], settings["night_contrast"])
    except Exception as e:
        print("Time check error:", e)

# Function to run scheduled tasks
def schedule_runner():
    schedule.every().minute.do(apply_current_brightness_contrast)  # Apply every minute to check time
    
    while True:
        schedule.run_pending()  # Run scheduled tasks        
        time.sleep(1) # Check every minute

# Create scheduled tasks
def update_scheduled_tasks():
    schedule.clear()
    try:
        schedule.every().day.at(settings["day_start"]).do(
            lambda: set_brightness_contrast(settings["day_brightness"], settings["day_contrast"])
        )
        schedule.every().day.at(settings["day_end"]).do(
            lambda: set_brightness_contrast(settings["night_brightness"], settings["night_contrast"])
        )
    except ValueError as e:
        print("Scheduling format error:", e)

update_scheduled_tasks() # Update scheduled tasks for the first start

active_shortcuts = []   # List to keep track of active shortcuts

# Function to clear keyboard shortcuts
def clear_keyboard_shortcuts():
    for shortcut in active_shortcuts:
        keyboard.remove_hotkey(shortcut) # Remove the shortcut
        active_shortcuts.clear()

# Change mode with keyboard shortcuts
def setup_keyboard_shortcuts():
    clear_keyboard_shortcuts() # Clear existing shortcuts
    """Set up keyboard shortcuts for day and night modes."""
    active_shortcuts.append(keyboard.add_hotkey(settings["day_shortcut"], lambda: set_brightness_contrast(settings["day_brightness"], settings["day_contrast"])))
    active_shortcuts.append(keyboard.add_hotkey(settings["night_shortcut"], lambda: set_brightness_contrast(settings["night_brightness"], settings["night_contrast"])))
    
setup_keyboard_shortcuts() # Set shortcuts for the first start

# System tray icon and menu
from PIL import Image, ImageDraw

# Create an image for the system tray icon
def create_image():
    """
    Creates an icon to indicate monitor settings.
    A framed square in the center with a sun symbol and monitor stand below.
    """
    img = Image.new("RGB", (64, 64), (0, 0, 0))  # Black background
    d = ImageDraw.Draw(img)

    # Framed square
    frame_color = (100, 100, 100)  # Gray frame color
    frame_width = 4
    d.rectangle(
        [frame_width, frame_width, 64 - frame_width - 1, 64 - frame_width - 1],  # Leave space equal to frame width on edges
        outline=frame_color,
        width=frame_width,
    )

    # Sun symbol (white circle in the center)
    center_x = 32
    center_y = 32
    radius = 12
    d.ellipse((center_x - radius, center_y - radius, center_x + radius, center_y + radius), fill=(255, 255, 255))

    # Sun rays (lines)
    num_rays = 8  # Number of rays
    ray_length = 10  # Length of rays
    for i in range(num_rays):
        angle = i * 360 / num_rays
        import math
        x1 = center_x + radius * math.cos(math.radians(angle))
        y1 = center_y + radius * math.sin(math.radians(angle))
        x2 = center_x + (radius + ray_length) * math.cos(math.radians(angle))
        y2 = center_y + (radius + ray_length) * math.sin(math.radians(angle))
        d.line((x1, y1, x2, y2), fill=(255, 255, 255), width=2)  # White rays

    # Monitor stand
    stand_width = 20
    stand_height = 8
    stand_x = center_x - stand_width // 2
    stand_y = 64 - stand_height - 2  # Slightly above the frame
    d.rectangle(
        [stand_x, stand_y, stand_x + stand_width, stand_y + stand_height],
        fill=(150, 150, 150),  # Darker gray
    )

    # Base (optional)
    base_width = 30
    base_height = 3
    base_x = center_x - base_width // 2
    base_y = 64 - base_height
    d.rectangle(
        [base_x, base_y, base_x + base_width, base_y + base_height],
        fill=(100, 100, 100),
    )

    return img

# Time format validator function
def is_valid_time_format(t):
    return bool(re.match(r"^(?:[01]\d|2[0-3]):[0-5]\d$", t))

# Function to open the settings window
def open_settings_window():
    """Open the settings window."""
    def save_position(event=None):
        """Save the current position of the settings window."""
        settings["window_x"] = root_settings.winfo_x()
        settings["window_y"] = root_settings.winfo_y()
        save_settings(settings)    
    
    def save_settings_and_reload():
        """Save settings and reload the application."""
        # Validate and save settings
        global settings
        try:
            # Validate input values
            settings["day_brightness"] = int(entry_day_brightness.get())
            settings["night_brightness"] = int(entry_night_brightness.get())
            settings["day_contrast"] = int(entry_day_contrast.get())
            settings["night_contrast"] = int(entry_night_contrast.get())

            if not 1 <= settings["day_brightness"] <= 100 or not 1 <= settings["night_brightness"] <= 100:
                raise ValueError("Brightness values must be between 1 and 100.")
            if not 1 <= settings["day_contrast"] <= 100 or not 1 <= settings["night_contrast"] <= 100:
                raise ValueError("Contrast values must be between 1 and 100.")

            settings["day_start"] = entry_day_start.get()
            settings["day_end"] = entry_day_end.get()

            if not is_valid_time_format(settings["day_start"]) or not is_valid_time_format(settings["day_end"]):
                messagebox.showerror(title="Invalid Time Format", message="Please enter the time in HH:MM format. Example: 07:00")
                return

            # Automatically calculate night mode
            settings["night_start"] = settings["day_end"]
            settings["night_end"] = settings["day_start"]

            save_settings(settings)  # Save new settings to JSON
            settings = load_settings()  # Reload updated settings
           
            apply_current_brightness_contrast() # Apply immediately on save
            clear_keyboard_shortcuts() # Clear existing shortcuts
            setup_keyboard_shortcuts() # Set new shortcuts
            update_scheduled_tasks() # Update scheduled tasks
            show_success_message() # Show success message

            # Reflect updated values in the window
            entry_day_brightness.delete(0, tk.END)
            entry_day_brightness.insert(0, str(settings["day_brightness"]))
            entry_night_brightness.delete(0, tk.END)
            entry_night_brightness.insert(0, str(settings["night_brightness"]))
            entry_day_contrast.delete(0, tk.END)
            entry_day_contrast.insert(0, str(settings["day_contrast"]))
            entry_night_contrast.delete(0, tk.END)
            entry_night_contrast.insert(0, str(settings["night_contrast"]))

            entry_day_start.delete(0, tk.END)
            entry_day_start.insert(0, settings["day_start"])
            entry_day_end.delete(0, tk.END)
            entry_day_end.insert(0, settings["day_end"])

        except (ValueError, Exception) as e:
            messagebox.showerror(title="Error", message=str(e))            

    root_settings = tk.Tk()
    root_settings.title("Settings")
    window_x = settings.get("window_x", 100)
    window_y = settings.get("window_y", 100)
    root_settings.geometry(f"250x420+{window_x}+{window_y}")
    root_settings.resizable(False, False)  # Disable resizing of the window

    # Bind the window movement event to save the position
    root_settings.bind("<Configure>", save_position)
    
    # Create the settings window
    tk.Label(root_settings, text="Day Mode - Brightness (%)").pack()
    entry_day_brightness = tk.Entry(root_settings)
    entry_day_brightness.insert(0, str(settings["day_brightness"]))
    entry_day_brightness.pack()

    ## Day Mode - Contrast (%)
    tk.Label(root_settings, text="Day Mode - Contrast (%)").pack()
    entry_day_contrast = tk.Entry(root_settings)
    entry_day_contrast.insert(0, str(settings["day_contrast"]))
    entry_day_contrast.pack()

    ## Night Mode - Brightness (%)
    tk.Label(root_settings, text="Night Mode - Brightness (%)").pack()
    entry_night_brightness = tk.Entry(root_settings)
    entry_night_brightness.insert(0, str(settings["night_brightness"]))
    entry_night_brightness.pack()

    ## Night Mode - Contrast (%)
    tk.Label(root_settings, text="Night Mode - Contrast (%)").pack()
    entry_night_contrast = tk.Entry(root_settings)
    entry_night_contrast.insert(0, str(settings["night_contrast"]))
    entry_night_contrast.pack()

    ## Display day start time (readonly)
    tk.Label(root_settings, text="Day Start (HH:MM)").pack()
    entry_day_start = tk.Entry(root_settings)
    entry_day_start.insert(0, settings["day_start"])
    entry_day_start.pack()

    ## Display day end time (readonly)
    tk.Label(root_settings, text="Day End (HH:MM)").pack()
    entry_day_end = tk.Entry(root_settings)
    entry_day_end.insert(0, settings["day_end"])
    entry_day_end.pack()

    # Display night start and end times (readonly)
    tk.Label(root_settings, text=f"Night Start: {settings['night_start']}").pack()
    tk.Label(root_settings, text=f"Night End: {settings['night_end']}").pack()

    ## Day Mode - Shortcut
    tk.Label(root_settings, text="Day Mode - Shortcut").pack()
    tk.Label(root_settings, text=str(settings["day_shortcut"])).pack()

    ## Night Mode - Shortcut
    tk.Label(root_settings, text="Night Mode - Shortcut").pack()
    tk.Label(root_settings, text=str(settings["night_shortcut"])).pack()

    button_frame = tk.Frame(root_settings)
    button_frame.pack(pady=10)

    def enable_save_button(*args):
        """Enable the save button when any entry is modified."""        
        btn_save.config(state="normal") # Enable the save button

    def show_success_message():
        """Show a success message when settings are saved."""
        messagebox.showinfo("Success", "Your settings have been successfully saved.")
        btn_save.config(state="disabled") # Disable the save button after saving
    
    ## Save button
    btn_save = tk.Button(button_frame, text="Save", command=save_settings_and_reload,width=12,height=1,state="disabled")
    btn_save.pack(side="left", padx=5)

    ## Close button
    btn_close = tk.Button(button_frame, text="Close", command=lambda: close_settings_window(root_settings),width=12,height=1)
    btn_close.pack(side="left", padx=5)

    for entry in [entry_day_brightness, entry_night_brightness, entry_day_contrast, entry_night_contrast, entry_day_start, entry_day_end]:
        entry.bind("<KeyRelease>", enable_save_button) # Enable save button on key release
        entry.bind("<FocusOut>", enable_save_button)
    ## Apply button
    root_settings.mainloop()

# System tray menu
menu = Menu(
    MenuItem("Day Mode", lambda: set_brightness_contrast(settings["day_brightness"], settings["day_contrast"])),
    MenuItem("Night Mode", lambda: set_brightness_contrast(settings["night_brightness"], settings["night_contrast"])),
    MenuItem("Settings", open_settings_window),
    MenuItem("Exit", lambda icon: icon.stop() or os._exit(0))
)

icon = Icon("brightness_control", create_image(), menu=menu)

# def wait_for_monitor_ready():
#     """Monitörün DDC/CI üzerinden veri sağlamasını bekler."""
#     retries = 10  # Maksimum deneme sayısı
#     for i in range(retries):
#         try:
#             with get_monitors()[0] as monitor:
#                 if monitor.get_vcp_capabilities():
#                     print(f"✅ Monitör hazır, parlaklık uygulanıyor... Zaman: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
#                     return True
#         except:
#             print(f"⏳ Monitör hazır değil, tekrar deneme {i + 1}/{retries} Zaman: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
#             time.sleep(2)  # 2 saniye bekle ve tekrar dene

def wait_for_monitor_ready():
    """Monitörün DDC/CI üzerinden veri sağlamasını bekler ve zaman ölçümü yapar."""
    retries = 10  # Maksimum deneme sayısı
    delay = 2  # Her deneme arasında bekleme süresi
    start_time = time.time()  # Başlangıç zamanını kaydet

    for i in range(retries):
        iteration_start = time.time()  # Her döngü başlangıcını kaydet
        try:
            monitors = get_monitors()
            if monitors:
                with monitors[0] as monitor:
                    capabilities = monitor.get_vcp_capabilities()
                    if capabilities:
                        total_time = time.time() - start_time  # Toplam geçen süre
                        print(f"✅ Monitör hazır! Toplam geçen süre: {total_time:.2f} saniye")
                        return True

            elapsed_time = time.time() - iteration_start  # Döngü içinde geçen süre
            print(f"⏳ Monitör hazır değil, tekrar deneme {i + 1}/{retries} | Geçen süre: {elapsed_time:.2f} saniye")

        except Exception as e:
            print(f"⚠️ Beklenmeyen hata oluştu: {e}")

        time.sleep(delay)  # Belirtilen süre kadar bekle ve tekrar dene

    print("❌ Monitör hazır hale gelmedi. Alternatif bir hata yönetimi gerekiyor.")
    return False


def handle_screen_wake_event():
    """Ekran uyandıktan sonra parlaklık ve kontrastı tekrar uygular."""
    print(f"🔹 Ekran uyandı, parlaklık ve kontrast tekrar uygulanıyor...")
    wait_for_monitor_ready()  # Monitörün hazır olmasını bekle
    apply_current_brightness_contrast()

def start_system_tray():
    try:
        time.sleep(2)  # Sistem tepsisinin başlatılmasını bekle
        icon.run()
    except KeyError as e:
        print(f"❌ PyStray sistem hatası: {e}")


class SYSTEM_POWER_STATUS(ctypes.Structure):
    _fields_ = [
        ("ACLineStatus", ctypes.c_byte),
        ("BatteryFlag", ctypes.c_byte),
        ("BatteryLifePercent", ctypes.c_byte),
        ("Reserved1", ctypes.c_byte),
        ("BatteryLifeTime", ctypes.c_ulong),
        ("BatteryFullLifeTime", ctypes.c_ulong),
    ]

def detect_wake_up():
    """Windows Event Log üzerinden uyandırma olaylarını takip eder."""
    print("Uyandırma olayları dinleniyor...")

    while True:
        try:
            log_output = subprocess.check_output(["wevtutil", "qe", "System", "/c:1", "/rd:true", "/f:text"], stderr=subprocess.STDOUT, text=True)
            if "Event ID: 1" in log_output:  # Ekran uyandırma olayı
                print(f"🔹 Event ID: 1 Ekran uyandırma olayı tespit edildi, parlaklık uygulanıyor! Zaman: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
                handle_screen_wake_event()
            elif "Event ID: 42" in log_output:  # Uyandırma olayları
                print(f"🔹Event ID: 42 Uyandırma olayı tespit edildi, parlaklık uygulanıyor! Zaman: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
                handle_screen_wake_event()
            if "Power-Troubleshooter" in log_output:  # Uyandırma olayları bu kayıttan geçer
                print(f"🔹Power-Troubleshooter Uyandırma olayı tespit edildi, parlaklık uygulanıyor! Zaman: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
                handle_screen_wake_event()

        except subprocess.CalledProcessError:
            print("XXX Windows Event Log okunurken hata oluştu.")

        time.sleep(5)  # 5 saniyede bir kontrol et (ama sadece yeni olayları takip et!)

# Main loop
if __name__ == "__main__":    
    try:
        wake_up_thread = threading.Thread(target=detect_wake_up)
        wake_up_thread.daemon = True
        wake_up_thread.start()
        add_to_startup()
        wait_for_monitor_ready()  # Wait for the monitor to be ready before applying brightness
        schedule_thread = threading.Thread(target=schedule_runner)
    except Exception as e:
        print(f"❌ Thread hatası: {e}")
    
    apply_current_brightness_contrast()  # Apply immediately on startup
    icon.run() # Run the system tray icon
