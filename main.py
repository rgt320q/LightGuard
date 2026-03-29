import tkinter as tk
from tkinter import ttk
import json
import os
import keyboard
import threading
import queue
import time
import schedule
from pystray import Icon, MenuItem, Menu
from monitorcontrol import get_monitors
from PIL import Image, ImageDraw
from datetime import datetime
import signal
import sys
import re
import subprocess
try:
    import win32con
    import win32gui
    import win32api
    have_pywin32 = True
except Exception:
    have_pywin32 = False

# UI palette globals (initialized at GUI startup)
ACCENT_COLOR = '#0078D7'
BG_COLOR = '#0F0F0F'
FG_COLOR = '#FFFFFF'
# countdown globals used by toast code (declare here to avoid undefined warnings)
countdown_toast = None
countdown_active = False
countdown_cancelled = False

# single settings window handle
settings_win = None

# Simple translation infrastructure (Turkish)
LANG = 'tr'
TRANSLATIONS = {
    'tr': {
        'app_name': 'LightGuard',
        'day_mode': 'Gündüz Modu',
        'night_mode': 'Gece Modu',
        'settings': 'Ayarlar',
        'exit': 'Çıkış',
        'brightness': 'Parlaklık:',
        'contrast': 'Kontrast:',
        'day_start_label': 'Gün Başlangıcı (HH:MM):',
        'day_end_label': 'Gün Bitişi (HH:MM):',
        'save': 'Kaydet',
        'apply': 'Uygula',
        'close': 'Kapat',
        'invalid_time_title': 'Geçersiz Saat',
        'invalid_time_msg': 'Lütfen saatleri HH:MM formatında girin.',
        'saved_title': 'Kaydedildi',
        'saved_msg': 'Ayarlar kaydedildi.',
        'press_ctrl_alt_s': 'Ayarları açmak için Ctrl+Alt+S tuşuna basın.',
        'press_ctrl_alt_a': 'Ayarları uygulamak için Ctrl+Alt+A tuşuna basın.',
        'shutting_down': 'LightGuard kapatılıyor...',
        'power_listener_disabled': 'pywin32 bulunamadı: güç olayı dinleyicisi devre dışı',
        'power_listener_started': 'Güç olayı dinleyicisi başlatıldı',
        'language': 'Dil',
        'english': 'English',
        'turkish': 'Türkçe',
        'schedule': 'Zamanlama',
        'cancel': 'İptal',
        'countdown_toast': 'LightGuard {sec} saniye sonra monitör ışık modunuzu uygulayacak.',
        'countdown_finished': 'Geri sayım sona erdi. Ayarlar uygulanıyor.',
        'toast_app_name': 'LightGuard'
    },
    'en': {
        'app_name': 'LightGuard',
        'day_mode': 'Day Mode',
        'night_mode': 'Night Mode',
        'settings': 'Settings',
        'exit': 'Exit',
        'brightness': 'Brightness:',
        'contrast': 'Contrast:',
        'day_start_label': 'Day Start (HH:MM):',
        'day_end_label': 'Day End (HH:MM):',
        'save': 'Save',
        'apply': 'Apply',
        'close': 'Close',
        'invalid_time_title': 'Invalid Time',
        'invalid_time_msg': 'Please enter times in HH:MM format.',
        'saved_title': 'Saved',
        'saved_msg': 'Settings saved.',
        'press_ctrl_alt_s': 'Press Ctrl+Alt+S to open settings.',
        'press_ctrl_alt_a': 'Press Ctrl+Alt+A to apply settings.',
        'shutting_down': 'LightGuard shutting down...',
        'power_listener_disabled': 'pywin32 not found: power listener disabled',
        'power_listener_started': 'Power listener started',
        'language': 'Language',
        'english': 'English',
        'turkish': 'Turkish',
        'schedule': 'Schedule',
        'cancel': 'Cancel',
        'countdown_toast': 'LightGuard will apply the display profile in {sec} seconds.',
        'countdown_finished': 'Countdown finished. Applying settings.',
        'toast_app_name': 'LightGuard'
    }
}


def tr(key, default=None):
    try:
        lang_map = TRANSLATIONS.get(globals().get('LANG', LANG), {})
        if key in lang_map:
            return lang_map[key]
        # fallback to English map if available
        en_map = TRANSLATIONS.get('en', {})
        if key in en_map:
            return en_map[key]
    except Exception:
        pass
    return default if default is not None else key

def get_windows_accent_color():
    """Try to obtain the current Windows accent color via DwmGetColorizationColor.
    Returns a hex color string like '#rrggbb' or None on failure.
    """
    try:
        if sys.platform != 'win32':
            return None
        from ctypes import wintypes, windll, byref, c_uint, c_bool
        color = c_uint()
        opaque = c_bool()
        res = windll.dwmapi.DwmGetColorizationColor(byref(color), byref(opaque))
        if res == 0:
            clr = color.value
            # DwmGetColorizationColor returns a DWORD where lowest bytes are R,G,B
            r = clr & 0xFF
            g = (clr >> 8) & 0xFF
            b = (clr >> 16) & 0xFF
            return f'#{r:02x}{g:02x}{b:02x}'
    except Exception:
        pass
    return None


def init_ui_palette():
    """Initialize ACCENT_COLOR, BG_COLOR, FG_COLOR and configure ttk styles.
    Call after `gui_root` has been created.
    """
    global ACCENT_COLOR, BG_COLOR, FG_COLOR
    try:
        accent = get_windows_accent_color()
        if accent:
            ACCENT_COLOR = accent
        # keep dark background / light foreground consistent with existing toast
        BG_COLOR = '#0F0F0F'
        FG_COLOR = '#FFFFFF'
        try:
            style = ttk.Style()
            try:
                style.theme_use('clam')
            except Exception:
                pass
            style.configure('App.TFrame', background=BG_COLOR)
            style.configure('App.TLabel', background=BG_COLOR, foreground=FG_COLOR, font=('Segoe UI', 10))
            # LabelFrame style (so frames blend with background and header uses clear text)
            style.configure('App.TLabelframe', background=BG_COLOR, bordercolor=ACCENT_COLOR)
            style.configure('App.TLabelframe.Label', background=BG_COLOR, foreground=FG_COLOR, font=('Segoe UI', 10, 'bold'))
            # Entry / Spinbox fields
            try:
                style.configure('TEntry', fieldbackground='#1E1E1E', background='#1E1E1E', foreground=FG_COLOR)
            except Exception:
                pass
            try:
                style.configure('TSpinbox', fieldbackground='#1E1E1E', background='#1E1E1E', foreground=FG_COLOR)
            except Exception:
                pass
            # Scale styling (best-effort)
            try:
                style.configure('Horizontal.TScale', troughcolor='#2A2A2A', background=BG_COLOR)
            except Exception:
                pass
            # Buttons: accent and neutral
            style.configure('Accent.TButton', background=ACCENT_COLOR, foreground=FG_COLOR, relief='flat', padding=6)
            style.map('Accent.TButton',
                      background=[('active', '#005A9E'), ('!disabled', ACCENT_COLOR)],
                      foreground=[('disabled', '#AAAAAA'), ('!disabled', FG_COLOR)])
            style.configure('Neutral.TButton', background='#262626', foreground=FG_COLOR, relief='flat', padding=6)
            style.map('Neutral.TButton',
                      background=[('active', '#2E2E2E'), ('!disabled', '#262626')],
                      foreground=[('disabled', '#777777'), ('!disabled', FG_COLOR)])
            # subtle frame border for sections
            style.configure('App.TFrame', background=BG_COLOR, borderwidth=0)
            style.configure('Toast.TFrame', background=BG_COLOR)
            style.configure('Toast.TLabel', background=BG_COLOR, foreground=FG_COLOR, font=('Segoe UI', 10))
        except Exception:
            pass
    except Exception:
        ACCENT_COLOR = '#0078D7'
        BG_COLOR = '#0F0F0F'
        FG_COLOR = '#FFFFFF'

# logging to file for persistent diagnostics
import logging
logger = logging.getLogger('lightguard')
if not logger.handlers:
    logger.setLevel(logging.INFO)
    fh = logging.FileHandler('lightguard.log', encoding='utf-8')
    fh.setFormatter(logging.Formatter('%(asctime)s %(levelname)s %(message)s'))
    logger.addHandler(fh)
    # also mirror to console
    ch = logging.StreamHandler()
    ch.setFormatter(logging.Formatter('%(asctime)s %(levelname)s %(message)s'))
    logger.addHandler(ch)

def load_settings():
    if os.path.exists("settings.json"):
        with open("settings.json", "r") as f:
            return json.load(f)
    return {
        "day_brightness": "100",
        "night_brightness": "50",
        "day_contrast": "100",
        "night_contrast": "70",
        "day_start": "08:00",
        "day_end": "18:00"
        ,"lang": "tr"
    }


def ensure_settings_file():
    """Ensure a `settings.json` exists on disk. If not, write defaults returned by `load_settings()`.
    This helps installed copies have a concrete settings file for the application and for the
    installer to overwrite with a packaged default.
    """
    try:
        if not os.path.exists('settings.json'):
            s = load_settings()
            with open('settings.json', 'w', encoding='utf-8') as f:
                json.dump(s, f, indent=4)
    except Exception:
        pass


# Initialize LANG from persisted settings if present
try:
    try:
        LANG = load_settings().get('lang', LANG)
    except Exception:
        pass
except Exception:
    pass

# ensure a concrete settings.json file exists for first-run / installer scenarios
try:
    ensure_settings_file()
except Exception:
    pass

def apply_settings():
    settings = load_settings()
    # Apply settings according to current_mode and schedule.
    try:
        # decide which profile to apply and log for diagnostics
        if current_mode == 'day':
            mode = 'day'
            b = settings.get('day_brightness', '100')
            c = settings.get('day_contrast', '100')
        elif current_mode == 'night':
            mode = 'night'
            b = settings.get('night_brightness', '50')
            c = settings.get('night_contrast', '70')
        else:
            if is_day_mode():
                mode = 'day'
                b = settings.get('day_brightness', '100')
                c = settings.get('day_contrast', '100')
            else:
                mode = 'night'
                b = settings.get('night_brightness', '50')
                c = settings.get('night_contrast', '70')
        print(f"apply_settings: selected mode='{mode}', brightness={b}, contrast={c}")
        success = set_brightness_contrast(b, c)
        print(f"apply_settings: apply result={success}")
        return success
    except Exception as e:
        print("Error applying settings:", e)
        return False

def save_settings():
    # Save settings from the settings window variables if available,
    # otherwise fallback to existing settings file behavior.
    try:
        settings = {
            "day_brightness": str(day_brightness_var.get()),
            "night_brightness": str(night_brightness_var.get()),
            "day_contrast": str(day_contrast_var.get()),
            "night_contrast": str(night_contrast_var.get()),
            "day_start": day_start_var.get(),
            "day_end": day_end_var.get()
        }
    except Exception:
        # fallback if variables not present
        if os.path.exists("settings.json"):
            with open("settings.json", "r") as f:
                settings = json.load(f)
        else:
            settings = {}

    with open("settings.json", "w") as f:
        # include language preference if available
        try:
            settings['lang'] = globals().get('lang_var').get()
        except Exception:
            try:
                # try reading persisted value
                settings['lang'] = load_settings().get('lang', LANG)
            except Exception:
                settings['lang'] = LANG
        json.dump(settings, f, indent=4)

    try:
        save_button.config(state='disabled')
    except Exception:
        pass

    global current_mode
    try:
        current_mode = 'auto'
    except Exception:
        pass

    try:
        update_tray_menu()
    except Exception:
        pass

def enable_save_button(event=None):
    save_button.config(state='normal')

def open_settings_window():
    """Request the main GUI loop to show settings window.

    This enqueues a callable so that all tkinter operations run on
    the single GUI thread (mainloop), avoiding cross-thread Tk usage.
    """
    try:
        enqueue_gui_call(show_settings_window)
    except Exception:
        # fallback: attempt to show directly (best-effort)
        try:
            show_settings_window()
        except Exception:
            pass


def enqueue_gui_call(func, *args, **kwargs):
    global gui_queue
    if 'gui_queue' not in globals() or gui_queue is None:
        return
    gui_queue.put((func, args, kwargs))


def process_gui_queue():
    global gui_queue, gui_root
    try:
        while not gui_queue.empty():
            func, args, kwargs = gui_queue.get_nowait()
            try:
                func(*args, **kwargs)
            except Exception as e:
                print("GUI task error:", e)
    except Exception:
        pass
    # schedule next poll if root is alive
    try:
        if gui_root is not None:
            gui_root.after(100, process_gui_queue)
    except Exception:
        pass


def show_settings_window():
    """Create a non-blocking settings window attached to the shared `gui_root`."""
    global save_button
    global day_brightness_var, night_brightness_var, day_contrast_var, night_contrast_var
    global day_start_var, day_end_var
    global settings_win
    global lang_var

    settings = load_settings()

    # If settings window already exists, bring to front and return
    try:
        if settings_win is not None:
            try:
                settings_win.lift()
                settings_win.attributes('-topmost', True)
                settings_win.after_idle(settings_win.attributes, '-topmost', False)
                return
            except Exception:
                # stale handle; continue to create a fresh window
                try:
                    settings_win.destroy()
                except Exception:
                    pass
                settings_win = None
    except Exception:
        pass

    # create Toplevel window attached to gui_root
    win = tk.Toplevel(gui_root)
    settings_win = win
    # hide native title bar so we can draw a custom accent header
    try:
        win.overrideredirect(True)
    except Exception:
        pass
    win.title(f"{tr('settings','Ayarlar')} - {tr('app_name','LightGuard')}")
    # restore previous geometry if present
    try:
        geom = settings.get('settings_geometry')
        if geom:
            win.geometry(geom)
        else:
            win.geometry("420x380")
    except Exception:
        win.geometry("420x380")
    win.resizable(False, False)

    try:
        style = ttk.Style(win)
        try:
            style.theme_use('clam')
        except Exception:
            pass
    except Exception:
        pass

    try:
        win.configure(background=globals().get('BG_COLOR', '#0F0F0F'))
    except Exception:
        pass

    # Header area: custom app logo + title with accent background and window controls
    try:
        header_bg = globals().get('ACCENT_COLOR', ACCENT_COLOR)
        header = tk.Frame(win, bg=header_bg, height=44)
        header.pack(fill=tk.X, side=tk.TOP)
        header.pack_propagate(False)
        try:
            from PIL import ImageTk
            img = create_image().resize((24, 24), Image.LANCZOS)
            header_icon = ImageTk.PhotoImage(img)
        except Exception:
            header_icon = None

        try:
            if header_icon is not None:
                icon_lbl = tk.Label(header, image=header_icon, bg=header_bg)
                icon_lbl.image = header_icon
                icon_lbl.pack(side=tk.LEFT, padx=(12, 8), pady=8)
        except Exception:
            pass

        try:
            title_text = f"{tr('settings','Ayarlar')} - {tr('app_name','LightGuard')}"
            title_lbl = tk.Label(header, text=title_text, bg=header_bg, fg=globals().get('FG_COLOR', '#FFFFFF'), anchor='w', font=('Segoe UI', 11, 'bold'))
            title_lbl.pack(side=tk.LEFT, padx=(6, 12), pady=8)
        except Exception:
            pass

        # window control buttons (minimize, maximize/restore, close)
        try:
            btn_frame = tk.Frame(header, bg=header_bg)
            btn_frame.pack(side=tk.RIGHT, padx=6, pady=6)

            def _on_close():
                try:
                    _cleanup_and_close()
                except Exception:
                    try:
                        win.destroy()
                    except Exception:
                        pass

            # only show close button
            try:
                close_btn = tk.Button(btn_frame, text='✕', command=_on_close, bg=header_bg, fg=globals().get('FG_COLOR', '#FFFFFF'), bd=0, relief='flat', padx=8, pady=2)
                close_btn.pack(side=tk.RIGHT)
            except Exception:
                pass

            # enable dragging the window by the header
            try:
                drag_data = {'x': 0, 'y': 0}
                def _start_move(e):
                    try:
                        drag_data['x'] = e.x
                        drag_data['y'] = e.y
                    except Exception:
                        pass
                def _do_move(e):
                    try:
                        x = win.winfo_x() + e.x - drag_data['x']
                        y = win.winfo_y() + e.y - drag_data['y']
                        win.geometry(f'+{x}+{y}')
                    except Exception:
                        pass
                header.bind('<Button-1>', _start_move)
                header.bind('<B1-Motion>', _do_move)
            except Exception:
                pass
        except Exception:
            pass
    except Exception:
        pass

    container = ttk.Frame(win, padding=12, style='App.TFrame')
    container.pack(fill=tk.BOTH, expand=True)
    try:
        container.configure(background=globals().get('BG_COLOR', '#0F0F0F'))
    except Exception:
        pass

    # create labelframe with a thin accent-colored border (works across themes)
    outer = tk.Frame(container, bg=globals().get('ACCENT_COLOR', ACCENT_COLOR), padx=1, pady=1)
    outer.pack(fill=tk.X, pady=6)
    day_frame = ttk.LabelFrame(outer, text=tr('day_mode','Gündüz Modu'), padding=10, style='App.TLabelframe')
    day_frame.pack(fill=tk.BOTH, expand=True)
    try:
        day_frame.configure(background=globals().get('BG_COLOR', '#0F0F0F'))
    except Exception:
        pass

    day_brightness_var = tk.IntVar(value=int(settings.get('day_brightness', '100')))
    ttk.Label(day_frame, text=tr('brightness','Parlaklık:'), style='App.TLabel').grid(row=0, column=0, sticky='w')
    # custom compact control: [-] [value entry] [+] to allow larger, styled buttons
    try:
        day_brightness_ctrl = tk.Frame(day_frame, bg=globals().get('BG_COLOR', '#0F0F0F'))
        day_brightness_ctrl.grid(row=0, column=1, sticky='w', padx=6)
        dec_btn = tk.Button(day_brightness_ctrl, text='-', command=lambda v=day_brightness_var: v.set(max(1, v.get()-1)),
                            bg=globals().get('ACCENT_COLOR', ACCENT_COLOR), fg=globals().get('FG_COLOR', '#FFFFFF'), bd=0, relief='flat', width=3, font=('Segoe UI', 10, 'bold'))
        dec_btn.pack(side=tk.LEFT, padx=(0,6))
        day_brightness_spin = tk.Entry(day_brightness_ctrl, textvariable=day_brightness_var, width=6, bg='#1E1E1E', fg=globals().get('FG_COLOR', '#FFFFFF'), insertbackground=globals().get('FG_COLOR', '#FFFFFF'), relief='flat')
        day_brightness_spin.pack(side=tk.LEFT)
        inc_btn = tk.Button(day_brightness_ctrl, text='+', command=lambda v=day_brightness_var: v.set(min(100, v.get()+1)),
                            bg=globals().get('ACCENT_COLOR', ACCENT_COLOR), fg=globals().get('FG_COLOR', '#FFFFFF'), bd=0, relief='flat', width=3, font=('Segoe UI', 10, 'bold'))
        inc_btn.pack(side=tk.LEFT, padx=(6,0))
    except Exception:
        day_brightness_spin = tk.Spinbox(day_frame, from_=1, to=100, textvariable=day_brightness_var, width=6, bg='#1E1E1E', fg=globals().get('FG_COLOR', '#FFFFFF'), insertbackground=globals().get('FG_COLOR', '#FFFFFF'))
        day_brightness_spin.grid(row=0, column=1, sticky='w', padx=6)
    day_brightness_scale = tk.Scale(day_frame, from_=1, to=100, variable=day_brightness_var, orient=tk.HORIZONTAL, resolution=1,
                                     bg=globals().get('BG_COLOR', '#0F0F0F'), troughcolor='#2A2A2A', fg=globals().get('FG_COLOR', '#FFFFFF'),
                                     highlightthickness=0, bd=0, activebackground=globals().get('ACCENT_COLOR', '#0078D7'))
    day_brightness_scale.grid(row=0, column=2, sticky='ew', padx=6)

    day_contrast_var = tk.IntVar(value=int(settings.get('day_contrast', '100')))
    ttk.Label(day_frame, text=tr('contrast','Kontrast:'), style='App.TLabel').grid(row=1, column=0, sticky='w')
    try:
        day_contrast_ctrl = tk.Frame(day_frame, bg=globals().get('BG_COLOR', '#0F0F0F'))
        day_contrast_ctrl.grid(row=1, column=1, sticky='w', padx=6)
        dec_btn = tk.Button(day_contrast_ctrl, text='-', command=lambda v=day_contrast_var: v.set(max(1, v.get()-1)),
                            bg=globals().get('ACCENT_COLOR', ACCENT_COLOR), fg=globals().get('FG_COLOR', '#FFFFFF'), bd=0, relief='flat', width=3, font=('Segoe UI', 10, 'bold'))
        dec_btn.pack(side=tk.LEFT, padx=(0,6))
        day_contrast_spin = tk.Entry(day_contrast_ctrl, textvariable=day_contrast_var, width=6, bg='#1E1E1E', fg=globals().get('FG_COLOR', '#FFFFFF'), insertbackground=globals().get('FG_COLOR', '#FFFFFF'), relief='flat')
        day_contrast_spin.pack(side=tk.LEFT)
        inc_btn = tk.Button(day_contrast_ctrl, text='+', command=lambda v=day_contrast_var: v.set(min(100, v.get()+1)),
                            bg=globals().get('ACCENT_COLOR', ACCENT_COLOR), fg=globals().get('FG_COLOR', '#FFFFFF'), bd=0, relief='flat', width=3, font=('Segoe UI', 10, 'bold'))
        inc_btn.pack(side=tk.LEFT, padx=(6,0))
    except Exception:
        day_contrast_spin = tk.Spinbox(day_frame, from_=1, to=100, textvariable=day_contrast_var, width=6, bg='#1E1E1E', fg=globals().get('FG_COLOR', '#FFFFFF'), insertbackground=globals().get('FG_COLOR', '#FFFFFF'))
        day_contrast_spin.grid(row=1, column=1, sticky='w', padx=6)
    day_contrast_scale = tk.Scale(day_frame, from_=1, to=100, variable=day_contrast_var, orient=tk.HORIZONTAL, resolution=1,
                                   bg=globals().get('BG_COLOR', '#0F0F0F'), troughcolor='#2A2A2A', fg=globals().get('FG_COLOR', '#FFFFFF'),
                                   highlightthickness=0, bd=0, activebackground=globals().get('ACCENT_COLOR', '#0078D7'))
    day_contrast_scale.grid(row=1, column=2, sticky='ew', padx=6)

    outer2 = tk.Frame(container, bg=globals().get('ACCENT_COLOR', ACCENT_COLOR), padx=1, pady=1)
    outer2.pack(fill=tk.X, pady=6)
    night_frame = ttk.LabelFrame(outer2, text=tr('night_mode','Gece Modu'), padding=10, style='App.TLabelframe')
    night_frame.pack(fill=tk.BOTH, expand=True)
    try:
        night_frame.configure(background=globals().get('BG_COLOR', '#0F0F0F'))
    except Exception:
        pass

    night_brightness_var = tk.IntVar(value=int(settings.get('night_brightness', '50')))
    ttk.Label(night_frame, text=tr('brightness','Parlaklık:'), style='App.TLabel').grid(row=0, column=0, sticky='w')
    try:
        night_brightness_ctrl = tk.Frame(night_frame, bg=globals().get('BG_COLOR', '#0F0F0F'))
        night_brightness_ctrl.grid(row=0, column=1, sticky='w', padx=6)
        dec_btn = tk.Button(night_brightness_ctrl, text='-', command=lambda v=night_brightness_var: v.set(max(1, v.get()-1)),
                            bg=globals().get('ACCENT_COLOR', ACCENT_COLOR), fg=globals().get('FG_COLOR', '#FFFFFF'), bd=0, relief='flat', width=3, font=('Segoe UI', 10, 'bold'))
        dec_btn.pack(side=tk.LEFT, padx=(0,6))
        night_brightness_spin = tk.Entry(night_brightness_ctrl, textvariable=night_brightness_var, width=6, bg='#1E1E1E', fg=globals().get('FG_COLOR', '#FFFFFF'), insertbackground=globals().get('FG_COLOR', '#FFFFFF'), relief='flat')
        night_brightness_spin.pack(side=tk.LEFT)
        inc_btn = tk.Button(night_brightness_ctrl, text='+', command=lambda v=night_brightness_var: v.set(min(100, v.get()+1)),
                            bg=globals().get('ACCENT_COLOR', ACCENT_COLOR), fg=globals().get('FG_COLOR', '#FFFFFF'), bd=0, relief='flat', width=3, font=('Segoe UI', 10, 'bold'))
        inc_btn.pack(side=tk.LEFT, padx=(6,0))
    except Exception:
        night_brightness_spin = tk.Spinbox(night_frame, from_=1, to=100, textvariable=night_brightness_var, width=6, bg='#1E1E1E', fg=globals().get('FG_COLOR', '#FFFFFF'), insertbackground=globals().get('FG_COLOR', '#FFFFFF'))
        night_brightness_spin.grid(row=0, column=1, sticky='w', padx=6)
    night_brightness_scale = tk.Scale(night_frame, from_=1, to=100, variable=night_brightness_var, orient=tk.HORIZONTAL, resolution=1,
                                      bg=globals().get('BG_COLOR', '#0F0F0F'), troughcolor='#2A2A2A', fg=globals().get('FG_COLOR', '#FFFFFF'),
                                      highlightthickness=0, bd=0, activebackground=globals().get('ACCENT_COLOR', '#0078D7'))
    night_brightness_scale.grid(row=0, column=2, sticky='ew', padx=6)

    night_contrast_var = tk.IntVar(value=int(settings.get('night_contrast', '70')))
    ttk.Label(night_frame, text=tr('contrast','Kontrast:'), style='App.TLabel').grid(row=1, column=0, sticky='w')
    try:
        night_contrast_ctrl = tk.Frame(night_frame, bg=globals().get('BG_COLOR', '#0F0F0F'))
        night_contrast_ctrl.grid(row=1, column=1, sticky='w', padx=6)
        dec_btn = tk.Button(night_contrast_ctrl, text='-', command=lambda v=night_contrast_var: v.set(max(1, v.get()-1)),
                            bg=globals().get('ACCENT_COLOR', ACCENT_COLOR), fg=globals().get('FG_COLOR', '#FFFFFF'), bd=0, relief='flat', width=3, font=('Segoe UI', 10, 'bold'))
        dec_btn.pack(side=tk.LEFT, padx=(0,6))
        night_contrast_spin = tk.Entry(night_contrast_ctrl, textvariable=night_contrast_var, width=6, bg='#1E1E1E', fg=globals().get('FG_COLOR', '#FFFFFF'), insertbackground=globals().get('FG_COLOR', '#FFFFFF'), relief='flat')
        night_contrast_spin.pack(side=tk.LEFT)
        inc_btn = tk.Button(night_contrast_ctrl, text='+', command=lambda v=night_contrast_var: v.set(min(100, v.get()+1)),
                            bg=globals().get('ACCENT_COLOR', ACCENT_COLOR), fg=globals().get('FG_COLOR', '#FFFFFF'), bd=0, relief='flat', width=3, font=('Segoe UI', 10, 'bold'))
        inc_btn.pack(side=tk.LEFT, padx=(6,0))
    except Exception:
        night_contrast_spin = tk.Spinbox(night_frame, from_=1, to=100, textvariable=night_contrast_var, width=6, bg='#1E1E1E', fg=globals().get('FG_COLOR', '#FFFFFF'), insertbackground=globals().get('FG_COLOR', '#FFFFFF'))
        night_contrast_spin.grid(row=1, column=1, sticky='w', padx=6)
    night_contrast_scale = tk.Scale(night_frame, from_=1, to=100, variable=night_contrast_var, orient=tk.HORIZONTAL, resolution=1,
                                    bg=globals().get('BG_COLOR', '#0F0F0F'), troughcolor='#2A2A2A', fg=globals().get('FG_COLOR', '#FFFFFF'),
                                    highlightthickness=0, bd=0, activebackground=globals().get('ACCENT_COLOR', '#0078D7'))
    night_contrast_scale.grid(row=1, column=2, sticky='ew', padx=6)

    outer3 = tk.Frame(container, bg=globals().get('ACCENT_COLOR', ACCENT_COLOR), padx=1, pady=1)
    outer3.pack(fill=tk.X, pady=6)
    time_frame = ttk.LabelFrame(outer3, text=tr('schedule','Zamanlama'), padding=10, style='App.TLabelframe')
    time_frame.pack(fill=tk.BOTH, expand=True)
    try:
        time_frame.configure(background=globals().get('BG_COLOR', '#0F0F0F'))
    except Exception:
        pass

    # Language selection (English / Türkçe)
    try:
        lang_var = tk.StringVar(value=settings.get('lang', LANG))
        def _on_lang_change():
            try:
                new = lang_var.get()
                globals()['LANG'] = new
            except Exception:
                pass
            try:
                s = load_settings()
                s['lang'] = new
                with open('settings.json', 'w') as sf:
                    json.dump(s, sf, indent=4)
            except Exception:
                pass
            try:
                # update tray menu to reflect new language immediately
                update_tray_menu()
            except Exception:
                pass
            try:
                # Rebuild the settings window so all widgets pick up the new language immediately.
                try:
                    geom = None
                    try:
                        geom = win.winfo_geometry()
                    except Exception:
                        geom = None
                    try:
                        win.destroy()
                    except Exception:
                        pass
                    try:
                        globals()['settings_win'] = None
                    except Exception:
                        pass
                    # schedule reopen briefly later to allow destroy to complete
                    if 'gui_root' in globals() and gui_root is not None:
                        try:
                            gui_root.after(150, show_settings_window)
                        except Exception:
                            show_settings_window()
                    else:
                        show_settings_window()
                except Exception:
                    # fallback: at least refresh title if rebuild failed
                    try:
                        title_lbl.config(text=f"{tr('settings','Ayarlar')} - {tr('app_name','LightGuard')}")
                    except Exception:
                        pass
            except Exception:
                pass

        lang_frame = tk.Frame(container, bg=globals().get('BG_COLOR', '#0F0F0F'))
        lang_frame.pack(fill=tk.X, pady=6)
        try:
            ttk.Label(lang_frame, text=tr('language','Dil'), style='App.TLabel').pack(side=tk.LEFT)
        except Exception:
            try:
                tk.Label(lang_frame, text=tr('language','Dil'), bg=globals().get('BG_COLOR', '#0F0F0F'), fg=globals().get('FG_COLOR', '#FFFFFF')).pack(side=tk.LEFT)
            except Exception:
                pass

        try:
            rb_tr = tk.Radiobutton(lang_frame, text=tr('turkish','Türkçe'), variable=lang_var, value='tr', command=_on_lang_change, bg=globals().get('BG_COLOR', '#0F0F0F'), fg=globals().get('FG_COLOR', '#FFFFFF'), selectcolor=globals().get('BG_COLOR', '#0F0F0F'), activebackground=globals().get('BG_COLOR', '#0F0F0F'))
            rb_tr.pack(side=tk.LEFT, padx=8)
            rb_en = tk.Radiobutton(lang_frame, text=tr('english','English'), variable=lang_var, value='en', command=_on_lang_change, bg=globals().get('BG_COLOR', '#0F0F0F'), fg=globals().get('FG_COLOR', '#FFFFFF'), selectcolor=globals().get('BG_COLOR', '#0F0F0F'), activebackground=globals().get('BG_COLOR', '#0F0F0F'))
            rb_en.pack(side=tk.LEFT, padx=8)
        except Exception:
            pass
    except Exception:
        try:
            lang_var = tk.StringVar(value=LANG)
        except Exception:
            lang_var = None

    day_start_var = tk.StringVar(value=settings.get('day_start', '08:00'))
    day_end_var = tk.StringVar(value=settings.get('day_end', '18:00'))

    ttk.Label(time_frame, text=tr('day_start_label','Gün Başlangıcı (HH:MM):'), style='App.TLabel').grid(row=0, column=0, sticky='w')
    day_start_entry = ttk.Entry(time_frame, textvariable=day_start_var, width=10)
    day_start_entry.grid(row=0, column=1, sticky='w', padx=6)

    ttk.Label(time_frame, text=tr('day_end_label','Gün Bitişi (HH:MM):'), style='App.TLabel').grid(row=0, column=2, sticky='w')
    day_end_entry = ttk.Entry(time_frame, textvariable=day_end_var, width=10)
    day_end_entry.grid(row=0, column=3, sticky='w', padx=6)

    for frame in (day_frame, night_frame, time_frame):
        frame.columnconfigure(2, weight=1)

    btn_frame = tk.Frame(container, bg=globals().get('BG_COLOR', '#0F0F0F'))
    btn_frame.pack(fill=tk.X, pady=12)

    try:
        save_button = tk.Button(btn_frame, text=tr('save','Kaydet'), command=lambda: (save_settings(), show_saved_feedback(win)), state='disabled', bg=globals().get('ACCENT_COLOR', '#0078D7'), fg=globals().get('FG_COLOR', '#FFFFFF'), activebackground=globals().get('ACCENT_COLOR', '#005A9E'), relief='flat', padx=8, pady=4)
        save_button.pack(side=tk.RIGHT, padx=6)
    except Exception:
        save_button = tk.Button(btn_frame, text=tr('save','Kaydet'), command=lambda: (save_settings(), show_saved_feedback(win)), state='disabled')
        save_button.pack(side=tk.RIGHT, padx=6)

    try:
        apply_button = tk.Button(btn_frame, text=tr('apply','Uygula'), command=lambda: (apply_from_vars()), bg=globals().get('ACCENT_COLOR', '#0078D7'), fg=globals().get('FG_COLOR', '#FFFFFF'), activebackground=globals().get('ACCENT_COLOR', '#005A9E'), relief='flat', padx=8, pady=4)
        apply_button.pack(side=tk.RIGHT, padx=6)
    except Exception:
        apply_button = tk.Button(btn_frame, text=tr('apply','Uygula'), command=lambda: (apply_from_vars()))
        apply_button.pack(side=tk.RIGHT, padx=6)

    try:
        cancel_button = tk.Button(btn_frame, text=tr('close','Kapat'), command=lambda: win.destroy(), bg='#262626', fg=globals().get('FG_COLOR', '#FFFFFF'), activebackground='#2E2E2E', relief='flat', padx=8, pady=4)
        cancel_button.pack(side=tk.RIGHT, padx=6)
    except Exception:
        cancel_button = tk.Button(btn_frame, text=tr('close','Kapat'), command=lambda: win.destroy())
        cancel_button.pack(side=tk.RIGHT, padx=6)

    def validate_time_format(s):
        return bool(re.match(r"^(?:[01]\d|2[0-3]):[0-5]\d$", s))

    def on_var_change(*args):
        try:
            save_button.state(['!disabled'])
        except Exception:
            try:
                save_button.config(state='normal')
            except Exception:
                pass

    # Register traces and remember ids so we can remove them when the window closes.
    # This avoids callbacks executing when Tk variables are being garbage-collected
    # from a non-GUI thread which caused "main thread is not in main loop" errors.
    trace_ids = []
    for v in (day_brightness_var, day_contrast_var, night_brightness_var, night_contrast_var, day_start_var, day_end_var):
        try:
            tid = v.trace_add('write', lambda *a: on_var_change())
            trace_ids.append((v, 'write', tid))
        except Exception:
            try:
                # legacy trace
                tid = v.trace('w', lambda *a: on_var_change())
                trace_ids.append((v, 'w', tid))
            except Exception:
                pass

    def apply_from_vars():
        # validate times
        if not validate_time_format(day_start_var.get()) or not validate_time_format(day_end_var.get()):
            try:
                tk.messagebox.showerror(tr('invalid_time_title','Geçersiz Saat'), tr('invalid_time_msg','Lütfen saatleri HH:MM formatında girin.'), parent=win)
            except Exception:
                pass
            return
        # save settings
        new_settings = {
            "day_brightness": str(day_brightness_var.get()),
            "night_brightness": str(night_brightness_var.get()),
            "day_contrast": str(day_contrast_var.get()),
            "night_contrast": str(night_contrast_var.get()),
            "day_start": day_start_var.get(),
            "day_end": day_end_var.get()
        }
        try:
            # Merge with existing settings so we don't lose keys like 'lang' or geometry
            try:
                s = load_settings()
            except Exception:
                s = {}
            s.update(new_settings)
            try:
                # if language selector exists, persist current choice
                s['lang'] = globals().get('lang_var').get()
            except Exception:
                try:
                    s['lang'] = load_settings().get('lang', LANG)
                except Exception:
                    s['lang'] = LANG
            with open("settings.json", "w") as f:
                json.dump(s, f, indent=4)
        except Exception as e:
            print("Error saving settings:", e)

        try:
            update_scheduled_tasks(s)
        except Exception:
            pass

        if current_mode == 'day':
            set_brightness_contrast(new_settings.get('day_brightness', '100'), new_settings.get('day_contrast', '100'))
        elif current_mode == 'night':
            set_brightness_contrast(new_settings.get('night_brightness', '50'), new_settings.get('night_contrast', '70'))
        else:
            if is_day_mode():
                set_brightness_contrast(new_settings.get('day_brightness', '100'), new_settings.get('day_contrast', '100'))
            else:
                set_brightness_contrast(new_settings.get('night_brightness', '50'), new_settings.get('night_contrast', '70'))
        try:
            update_tray_menu()
        except Exception:
            pass

    def show_saved_feedback(w):
        try:
            tk.messagebox.showinfo(tr('saved_title','Kaydedildi'), tr('saved_msg','Ayarlar kaydedildi.'), parent=w)
        except Exception:
            pass

    # Adjust window size to ensure all controls (especially bottom buttons) are visible.
    try:
        win.update_idletasks()
        req_w = max(420, win.winfo_reqwidth())
        req_h = max(380, win.winfo_reqheight())
        # add small vertical margin so buttons aren't tight against the edge
        req_h += 24
        win.geometry(f"{req_w}x{req_h}")
    except Exception:
        pass

    # Ensure the window receives focus and accepts clicks reliably.
    try:
        win.lift()
        win.attributes('-topmost', True)
        win.after_idle(win.attributes, '-topmost', False)
    except Exception:
        pass

    def _cleanup_and_close():
        global settings_win
        # remove traces to avoid callbacks after variables are deleted
        for v, mode, tid in trace_ids:
            try:
                v.trace_remove(mode, tid)
            except Exception:
                try:
                    # older Tkinter variant
                    v.trace_vdelete(mode, tid)
                except Exception:
                    pass
        # persist geometry
        try:
            geom = win.geometry()
            s = load_settings()
            s['settings_geometry'] = geom
            with open("settings.json", "w") as f:
                json.dump(s, f, indent=4)
        except Exception:
            pass
        try:
            win.destroy()
        except Exception:
            pass
        try:
            settings_win = None
        except Exception:
            pass

    # Ensure cleanup when the window is closed by any means
    try:
        win.protocol('WM_DELETE_WINDOW', _cleanup_and_close)
        win.bind('<Destroy>', lambda e: _cleanup_and_close())
    except Exception:
        pass

def setup_keyboard_shortcuts():
    keyboard.add_hotkey("ctrl+alt+s", open_settings_window)
    keyboard.add_hotkey("ctrl+alt+a", apply_settings)

def create_image():
    from PIL import Image
    import math

    img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    # Monitor frame
    d.rounded_rectangle([6, 10, 58, 40], radius=4, fill=(40, 44, 52, 255), outline=(180, 185, 190, 255), width=2)

    # Screen area (darker)
    d.rectangle([10, 14, 54, 36], fill=(18, 22, 28, 255))

    # Sun (top-right of screen) with rays
    sun_cx, sun_cy = 44, 18
    sun_r = 7
    d.ellipse([sun_cx - sun_r, sun_cy - sun_r, sun_cx + sun_r, sun_cy + sun_r], fill=(255, 200, 0, 255))
    for i in range(8):
        angle = math.radians(i * 45)
        x1 = sun_cx + (sun_r + 1) * math.cos(angle)
        y1 = sun_cy + (sun_r + 1) * math.sin(angle)
        x2 = sun_cx + (sun_r + 6) * math.cos(angle)
        y2 = sun_cy + (sun_r + 6) * math.sin(angle)
        d.line((x1, y1, x2, y2), fill=(255, 210, 60, 255), width=2)

    # Monitor stand
    d.rectangle([28, 40, 36, 48], fill=(80, 86, 95, 255))
    d.rectangle([22, 48, 44, 52], fill=(60, 66, 75, 255))

    return img


def set_brightness_contrast(brightness, contrast):
    try:
        # normalize and clamp values to 0-100
        try:
            b = int(max(0, min(100, int(float(brightness)))))
        except Exception:
            try:
                b = int(brightness)
            except Exception:
                b = 50
        try:
            c = int(max(0, min(100, int(float(contrast)))))
        except Exception:
            try:
                c = int(contrast)
            except Exception:
                c = 50

        print(f"set_brightness_contrast: attempting to set brightness={b}, contrast={c}")
        monitors = get_monitors()
        try:
            mcount = len(monitors)
        except Exception:
            mcount = 0
        print(f"set_brightness_contrast: found {mcount} monitors")

        if not monitors:
            print("set_brightness_contrast: No monitors found to apply settings.")
            # don't return here; allow WMI fallback below to run when no monitors are detected
            # (scheduled-task or non-interactive sessions may not enumerate monitors)
            pass

        applied_any = False
        for idx, mon in enumerate(monitors):
            try:
                # try setting luminance and contrast with small retries; monitors may be flaky right after resume
                with mon as m:
                    # luminance retry
                    lum_ok = False
                    for lum_attempt in range(1, 4):
                        try:
                            m.set_luminance(b)
                            print(f"set_brightness_contrast: monitor[{idx}] set_luminance -> {b} (attempt {lum_attempt})")
                            lum_ok = True
                            break
                        except Exception as e:
                            print(f"set_brightness_contrast: monitor[{idx}] set_luminance failed (attempt {lum_attempt}):", e)
                            time.sleep(0.15)

                    # contrast retry
                    contrast_ok = False
                    for con_attempt in range(1, 4):
                        try:
                            m.set_contrast(c)
                            print(f"set_brightness_contrast: monitor[{idx}] set_contrast -> {c} (attempt {con_attempt})")
                            contrast_ok = True
                            break
                        except Exception as e:
                            print(f"set_brightness_contrast: monitor[{idx}] set_contrast failed (attempt {con_attempt}):", e)
                            time.sleep(0.15)

                    # small pause to let monitor apply settings, then try read-back
                    try:
                        time.sleep(0.05)
                    except Exception:
                        pass

                    # attempt to read back values if supported
                    try:
                        if hasattr(m, 'get_luminance'):
                            try:
                                current_b = m.get_luminance()
                                print(f"set_brightness_contrast: monitor[{idx}] read_luminance -> {current_b}")
                            except Exception as e:
                                print(f"set_brightness_contrast: monitor[{idx}] get_luminance failed:", e)
                        if hasattr(m, 'get_contrast'):
                            try:
                                current_c = m.get_contrast()
                                print(f"set_brightness_contrast: monitor[{idx}] read_contrast -> {current_c}")
                            except Exception as e:
                                print(f"set_brightness_contrast: monitor[{idx}] get_contrast failed:", e)
                                # try one more time after brief wait
                                try:
                                    time.sleep(0.1)
                                    current_c = m.get_contrast()
                                    print(f"set_brightness_contrast: monitor[{idx}] read_contrast (retry) -> {current_c}")
                                except Exception as e2:
                                    print(f"set_brightness_contrast: monitor[{idx}] get_contrast retry failed:", e2)
                    except Exception:
                        pass

                applied_any = True
            except Exception as e:
                print(f"set_brightness_contrast: monitor[{idx}] operation failed:", e)

        if not applied_any:
            print("set_brightness_contrast: No monitor operations succeeded.")
        # if we applied nothing via DDC/CI, try WMI fallback for internal displays (brightness only)
        if not applied_any:
            try:
                wmi_ok = _wmi_set_brightness(b)
                if wmi_ok:
                    print("set_brightness_contrast: WMI fallback applied brightness")
                    return True
            except Exception as e:
                print("set_brightness_contrast: WMI fallback failed:", e)
        return applied_any
    except Exception as e:
        print("Error applying brightness/contrast:", e)
        return False


def _wmi_set_brightness(level):
    """Attempt to set internal display brightness via WMI using PowerShell.
    Returns True on success.
    """
    try:
        lvl = int(max(0, min(100, int(level))))
    except Exception:
        lvl = 50
    try:
        # Use PowerShell WMI call to set brightness on internal panels
        cmd = f"powershell -Command \"(Get-WmiObject -Namespace root\\wmi -Class WmiMonitorBrightnessMethods).WmiSetBrightness(1,{lvl})\""
        # run without showing window
        res = subprocess.run(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=8)
        if res.returncode == 0:
            return True
        else:
            print("_wmi_set_brightness: command failed:", res.stderr.decode(errors='ignore'))
            return False
    except Exception as e:
        print("_wmi_set_brightness error:", e)
        return False


def monitors_ready(required=1):
    """Return True if at least `required` monitors are accessible and responsive."""
    try:
        mons = get_monitors()
        try:
            mcount = len(mons)
        except Exception:
            mcount = 0
        if mcount < required:
            return False

        # Try opening each monitor and doing a harmless read if possible
        for m in mons:
            try:
                with m as mm:
                    if hasattr(mm, 'get_luminance'):
                        try:
                            mm.get_luminance()
                        except Exception:
                            # this monitor not yet responsive
                            continue
                # at least one monitor was responsive
                return True
            except Exception:
                continue
        return False
    except Exception:
        return False


def wait_for_monitors_ready(timeout=30, poll=1.0, required=1):
    """Wait up to `timeout` seconds for monitors to become ready, polling every `poll` seconds."""
    start = time.time()
    while time.time() - start < timeout:
        if monitors_ready(required):
            return True
        time.sleep(poll)
    return False


def schedule_apply_after_delay(delay=10, target_mode=None):
    """Schedule an `apply_settings()` run after `delay` seconds.
    Uses `gui_root.after` when available to run on the GUI thread; falls back
    to a background timer otherwise. Ensures `current_mode` is set to 'auto'.
    """
    def _apply():
        try:
            global current_mode
            # If a target_mode was provided by the scheduler, apply that explicitly
            if target_mode in ('day', 'night'):
                current_mode = target_mode
            else:
                current_mode = 'auto'
        except Exception:
            pass

        try:
            update_scheduled_tasks(load_settings())
        except Exception:
            pass

        try:
            applied = apply_settings()
            logger.info(f'schedule_apply_after_delay: apply result={applied}')
        except Exception:
            logger.exception('schedule_apply_after_delay: apply_settings failed')

        try:
            try:
                enqueue_gui_call(update_tray_menu)
            except Exception:
                update_tray_menu()
        except Exception:
            pass

    # If GUI root is available, schedule toast creation on GUI thread
    try:
        if 'gui_root' in globals() and gui_root is not None:
            try:
                # ensure gui_queue exists
                if 'gui_queue' not in globals() or gui_queue is None:
                    # fallback to console
                    raise RuntimeError('gui_queue not initialized')

                remaining = int(max(0, int(delay)))

                def _create_toast(sec):
                    # run on GUI thread
                    try:
                        # remove existing
                        try:
                            if 'countdown_toast' in globals() and countdown_toast is not None:
                                try:
                                    countdown_toast.destroy()
                                except Exception:
                                    pass
                        except Exception:
                            pass

                        toast = tk.Toplevel(gui_root)
                        toast.overrideredirect(True)
                        toast.attributes('-topmost', True)
                        try:
                            toast.attributes('-alpha', 0.95)
                        except Exception:
                            pass

                        # use colors similar to Windows toast: dark background with accent border
                        frame = ttk.Frame(toast, relief='solid', borderwidth=1, padding=(8, 6))
                        frame.pack(fill=tk.BOTH, expand=True)
                        try:
                            # pick accent/bg/fg from UI palette initialized at GUI startup
                            accent = globals().get('ACCENT_COLOR', '#0078D7')
                            bg = globals().get('BG_COLOR', '#0F0F0F')
                            fg = globals().get('FG_COLOR', '#FFFFFF')
                            frame.config(style='Toast.TFrame')
                            style = ttk.Style()
                            style.configure('Toast.TFrame', background=bg)
                            style.configure('Toast.TLabel', background=bg, foreground=fg, font=('Segoe UI', 10))
                            style.configure('Toast.AppName', background=bg, foreground=fg, font=('Segoe UI', 10, 'bold'))

                            # left area: optional icon + app name + message stacked
                            info_frame = ttk.Frame(frame, style='Toast.TFrame')
                            info_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(6,8))

                            # attempt to create a small PhotoImage from our create_image() icon
                            photo = None
                            try:
                                from PIL import ImageTk
                                img = create_image().resize((32, 32), Image.LANCZOS)
                                photo = ImageTk.PhotoImage(img)
                            except Exception:
                                photo = None

                            if photo is not None:
                                icon_lbl = tk.Label(info_frame, image=photo, background=bg)
                                icon_lbl.image = photo
                                icon_lbl.pack(side=tk.LEFT, padx=(0,8))

                            texts_frame = ttk.Frame(info_frame, style='Toast.TFrame')
                            texts_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

                            # Use tk.Label with explicit bg/fg so text remains visible across themes
                            try:
                                app_lbl = tk.Label(texts_frame, text=tr('toast_app_name','LightGuard'), bg=bg, fg=fg, anchor='w', justify='left', font=('Segoe UI', 10, 'bold'))
                                app_lbl.pack(fill=tk.X, anchor='w')
                                lbl = tk.Label(texts_frame, text='', bg=bg, fg=fg, anchor='w', justify='left', wraplength=200, font=('Segoe UI', 10))
                                lbl.pack(fill=tk.X, anchor='w')
                            except Exception:
                                app_lbl = ttk.Label(texts_frame, text=tr('toast_app_name','LightGuard'), style='Toast.AppName', anchor='w', justify='left')
                                app_lbl.pack(fill=tk.X, anchor='w')
                                lbl = ttk.Label(texts_frame, text='', anchor='w', style='Toast.TLabel', justify='left')
                                lbl.pack(fill=tk.X, anchor='w')
                        except Exception:
                            lbl = ttk.Label(frame, text='', anchor='center')
                        def _cancel_toast():
                            try:
                                globals()['countdown_cancelled'] = True
                            except Exception:
                                pass
                            try:
                                logger.info('schedule_apply_after_delay: toast cancelled by user')
                            except Exception:
                                pass
                            try:
                                toast.destroy()
                            except Exception:
                                pass
                            try:
                                globals()['countdown_active'] = False
                            except Exception:
                                pass

                        try:
                            cancel_btn = ttk.Button(frame, text=tr('cancel','İptal'), command=_cancel_toast, style='Neutral.TButton')
                            cancel_btn.pack(side=tk.RIGHT, padx=(0,6))
                        except Exception:
                            pass

                        def update_position():
                            try:
                                sw = gui_root.winfo_screenwidth()
                                sh = gui_root.winfo_screenheight()
                                w = 360
                                h = 100
                                x = sw - w - 12
                                # Try to place the toast above the Windows taskbar by using the work area
                                try:
                                    from ctypes import wintypes, windll, byref, Structure
                                    class RECT(Structure):
                                        _fields_ = [('left', wintypes.LONG), ('top', wintypes.LONG), ('right', wintypes.LONG), ('bottom', wintypes.LONG)]
                                    rc = RECT()
                                    SPI_GETWORKAREA = 0x0030
                                    if windll.user32.SystemParametersInfoW(SPI_GETWORKAREA, 0, byref(rc), 0):
                                        work_bottom = rc.bottom
                                        y = max(12, work_bottom - h - 12)
                                    else:
                                        y = max(12, sh - h - 48)
                                except Exception:
                                    # fallback: place near bottom but above typical taskbar height
                                    y = max(12, sh - h - 48)
                                toast.geometry(f"{w}x{h}+{x}+{y}")
                                # ensure the label wraps to the toast width so text is fully visible
                                try:
                                    wrap_len = max(60, w - 140)
                                    lbl.config(wraplength=wrap_len, justify='left')
                                except Exception:
                                    pass
                                # adjust height to fit content if needed
                                try:
                                    toast.update_idletasks()
                                    req_h = max(h, frame.winfo_reqheight() + 8)
                                    y_adj = y
                                    try:
                                        # if work area available, ensure toast stays above taskbar
                                        from ctypes import wintypes, windll, byref, Structure
                                        class RECT(Structure):
                                            _fields_ = [('left', wintypes.LONG), ('top', wintypes.LONG), ('right', wintypes.LONG), ('bottom', wintypes.LONG)]
                                        rc = RECT()
                                        SPI_GETWORKAREA = 0x0030
                                        if windll.user32.SystemParametersInfoW(SPI_GETWORKAREA, 0, byref(rc), 0):
                                            work_bottom = rc.bottom
                                            y_adj = max(12, work_bottom - req_h - 12)
                                    except Exception:
                                        pass
                                    toast.geometry(f"{w}x{req_h}+{x}+{y_adj}")
                                except Exception:
                                    pass
                            except Exception:
                                pass

                        update_position()

                        def _tick(sec_inner):
                            # stop early if cancelled
                            try:
                                if globals().get('countdown_cancelled'):
                                    try:
                                        globals()['countdown_active'] = False
                                    except Exception:
                                        pass
                                    try:
                                        toast.destroy()
                                    except Exception:
                                        pass
                                    return
                            except Exception:
                                pass
                            try:
                                try:
                                    txt = tr('countdown_toast','LightGuard {sec} saniye sonra monitör ışık modunuzu uygulayacak.').format(sec=sec_inner)
                                except Exception:
                                    txt = f"LightGuard {sec_inner:2d}. saniye sonra monitör ışık modunuzu uygulayacak."
                                lbl.config(text=txt, justify='left')
                                # accent bar on the left
                                try:
                                    if not hasattr(toast, 'accent_bar'):
                                        ab = tk.Frame(toast, width=6, background=accent)
                                        ab.place(x=0, y=0, relheight=1)
                                        toast.accent_bar = ab
                                except Exception:
                                    pass
                            except Exception:
                                pass
                            # after updating text, ensure wrap length and resize toast to fit
                            try:
                                # recompute wrap and requested height
                                wrap_len = max(60, toast.winfo_width() - 140)
                                try:
                                    lbl.config(wraplength=wrap_len)
                                except Exception:
                                    pass
                                toast.update_idletasks()
                                new_h = max(100, frame.winfo_reqheight() + 8)
                                sw = gui_root.winfo_screenwidth()
                                sh = gui_root.winfo_screenheight()
                                x = sw - toast.winfo_width() - 12
                                # try to keep above taskbar
                                y = max(12, sh - new_h - 48)
                                try:
                                    from ctypes import wintypes, windll, byref, Structure
                                    class RECT(Structure):
                                        _fields_ = [('left', wintypes.LONG), ('top', wintypes.LONG), ('right', wintypes.LONG), ('bottom', wintypes.LONG)]
                                    rc = RECT()
                                    SPI_GETWORKAREA = 0x0030
                                    if windll.user32.SystemParametersInfoW(SPI_GETWORKAREA, 0, byref(rc), 0):
                                        work_bottom = rc.bottom
                                        y = max(12, work_bottom - new_h - 12)
                                except Exception:
                                    pass
                                toast.geometry(f"{toast.winfo_width()}x{new_h}+{x}+{y}")
                            except Exception:
                                pass
                            if sec_inner <= 0:
                                try:
                                    toast.destroy()
                                except Exception:
                                    pass
                                try:
                                    _apply()
                                except Exception:
                                    logger.exception('schedule_apply_after_delay: _apply failed')
                                # clear active flag
                                try:
                                    globals()['countdown_active'] = False
                                except Exception:
                                    pass
                                return
                            gui_root.after(1000, lambda: _tick(sec_inner - 1))

                        globals()['countdown_toast'] = toast
                        globals()['countdown_active'] = True
                        globals()['countdown_cancelled'] = False
                        _tick(sec)
                    except Exception:
                        logger.exception('schedule_apply_after_delay: failed to create toast')

                # avoid multiple simultaneous countdowns
                if globals().get('countdown_active'):
                    logger.info('schedule_apply_after_delay: countdown already active; skipping')
                    return

                try:
                    enqueue_gui_call(_create_toast, remaining)
                    logger.info(f'schedule_apply_after_delay: enqueued GUI countdown {delay}s')
                    return
                except Exception:
                    logger.exception('schedule_apply_after_delay: enqueue_gui_call failed')
                    # fallthrough to console fallback
            except Exception:
                logger.exception('schedule_apply_after_delay: GUI toast setup failed, falling back to console')
    except Exception:
        pass

    # fallback: start a console countdown (in background) and schedule the actual apply
    def _countdown_and_schedule():
        try:
            remaining = int(max(0, int(delay)))
        except Exception:
            remaining = int(delay)

        # visual countdown in console
        try:
            for sec in range(remaining, 0, -1):
                try:
                    try:
                        msg = tr('countdown_toast','LightGuard {sec} saniye sonra monitör ışık modunuzu uygulayacak.').format(sec=sec)
                    except Exception:
                        msg = f"LightGuard {sec:2d}. saniye sonra monitör ışık modunuzu uygulayacak..."
                    print(f"\r{msg}", end='', flush=True)
                except Exception:
                    pass
                time.sleep(1)
            try:
                try:
                    fin = tr('countdown_finished','Geri sayım sona erdi. Ayarlar uygulanıyor.')
                except Exception:
                    fin = 'Geri sayım sona erdi. Ayarlar uygulanıyor.'
                print(f"\r{fin}            ")
            except Exception:
                pass
        except Exception:
            pass

        # perform apply
        try:
            _apply()
        except Exception:
            try:
                logger.exception('schedule_apply_after_delay: _apply failed')
            except Exception:
                pass

    t = threading.Thread(target=_countdown_and_schedule, daemon=True)
    t.start()
    logger.info(f'schedule_apply_after_delay: started countdown and background apply in {delay}s')


def get_profile_values():
    """Return (mode, brightness, contrast) that should be applied according to current_mode and schedule."""
    try:
        settings = load_settings()
        if current_mode == 'day':
            mode = 'day'
            b = int(settings.get('day_brightness', '100'))
            c = int(settings.get('day_contrast', '100'))
        elif current_mode == 'night':
            mode = 'night'
            b = int(settings.get('night_brightness', '50'))
            c = int(settings.get('night_contrast', '70'))
        else:
            if is_day_mode():
                mode = 'day'
                b = int(settings.get('day_brightness', '100'))
                c = int(settings.get('day_contrast', '100'))
            else:
                mode = 'night'
                b = int(settings.get('night_brightness', '50'))
                c = int(settings.get('night_contrast', '70'))
        return mode, b, c
    except Exception:
        return 'auto', 100, 50



def ensure_persistence(target_b, target_c, timeout=60, poll=2.0, required_consecutive=3):
    """Poll monitors and ensure brightness/contrast stay at targets.
    If drift detected, reapply. Returns True if stabilized, False if timeout.
    """
    logger.info(f"ensure_persistence: target_b={target_b}, target_c={target_c}, timeout={timeout}s")
    start = time.time()
    consecutive = 0
    while time.time() - start < timeout:
        all_ok = True
        mons = []
        try:
            mons = get_monitors()
        except Exception:
            mons = []
        if not mons:
            logger.info('ensure_persistence: no monitors detected during check')
            all_ok = False
        else:
            for idx, m in enumerate(mons):
                try:
                    with m as mm:
                        b_ok = True
                        c_ok = True
                        if hasattr(mm, 'get_luminance'):
                            try:
                                cb = mm.get_luminance()
                                if int(cb) != int(target_b):
                                    b_ok = False
                            except Exception:
                                b_ok = False
                        if hasattr(mm, 'get_contrast'):
                            try:
                                cc = mm.get_contrast()
                                if int(cc) != int(target_c):
                                    c_ok = False
                            except Exception:
                                c_ok = False
                        if not (b_ok and c_ok):
                            logger.info(f"ensure_persistence: monitor[{idx}] mismatch (b_ok={b_ok}, c_ok={c_ok})")
                            all_ok = False
                except Exception:
                    logger.info(f"ensure_persistence: monitor[{idx}] access failed during check")
                    all_ok = False

        if all_ok:
            consecutive += 1
            logger.info(f"ensure_persistence: all_ok consecutive={consecutive}/{required_consecutive}")
            if consecutive >= required_consecutive:
                logger.info('ensure_persistence: stabilized')
                return True
        else:
            consecutive = 0
            logger.info('ensure_persistence: reapplying targets')
            try:
                set_brightness_contrast(target_b, target_c)
            except Exception:
                logger.exception('ensure_persistence: reapply failed')

        time.sleep(poll)

    logger.warning('ensure_persistence: timeout waiting for stability')
    return False


def is_day_mode():
    try:
        settings = load_settings()
        now = datetime.now().time()
        day_start = datetime.strptime(settings.get("day_start", "08:00"), "%H:%M").time()
        day_end = datetime.strptime(settings.get("day_end", "18:00"), "%H:%M").time()
        if day_start <= day_end:
            return day_start <= now < day_end
        else:
            return now >= day_start or now < day_end
    except Exception:
        return True


def is_night_mode():
    return not is_day_mode()


# current_mode: 'auto' (follow schedule), 'day', or 'night'
current_mode = 'auto'


def update_tray_menu():
    """Recreate the tray menu so checked state reflects `current_mode` or time."""
    if 'tray_icon' not in globals() or tray_icon is None:
        return

    def checked_day(item):
        if current_mode == 'auto':
            return is_day_mode()
        return current_mode == 'day'

    def checked_night(item):
        if current_mode == 'auto':
            return is_night_mode()
        return current_mode == 'night'

    def set_manual_day(icon, item):
        global current_mode
        current_mode = 'day'
        set_brightness_contrast(load_settings().get('day_brightness', '100'), load_settings().get('day_contrast', '100'))
        update_tray_menu()

    def set_manual_night(icon, item):
        global current_mode
        current_mode = 'night'
        set_brightness_contrast(load_settings().get('night_brightness', '50'), load_settings().get('night_contrast', '70'))
        update_tray_menu()

    new_menu = Menu(
        MenuItem(tr('day_mode','Gündüz Modu'), set_manual_day, checked=checked_day),
        MenuItem(tr('night_mode','Gece Modu'), set_manual_night, checked=checked_night),
        MenuItem(tr('settings','Ayarlar'), lambda icon, item: open_settings_window()),
        MenuItem(tr('exit','Çıkış'), lambda icon, item: (icon.stop(), os._exit(0)))
    )

    tray_icon.menu = new_menu
    try:
        tray_icon.update_menu()
    except Exception:
        pass


def schedule_runner():
    # ensure periodic apply job exists
    try:
        schedule.every().minute.do(lambda: apply_settings())
    except Exception:
        pass

    last_time = time.time()
    poll_interval = 1.0
    wake_threshold = 10.0  # seconds; if time jumped more than this, assume resume from sleep
    while True:
        try:
            now = time.time()
            # detect large time jumps (system resume from sleep/hybernation)
            if now - last_time > wake_threshold:
                try:
                    logger.info("System resume detected (time jump). Re-applying settings and updating schedule.")
                    # On resume, prefer returning to automatic scheduling mode
                    try:
                        global current_mode
                        previous_mode = current_mode
                        current_mode = 'auto'
                        logger.info(f"Mode on resume: was '{previous_mode}', set to 'auto'")
                    except Exception:
                        pass
                    # refresh scheduled tasks and retry applying settings with backoff
                    try:
                        update_scheduled_tasks(load_settings())
                    except Exception:
                        pass

                    # schedule a single apply after 30s (allow system to fully wake)
                    try:
                        schedule_apply_after_delay(10)
                    except Exception:
                        logger.exception('Resume: schedule_apply_after_delay failed')

                    # update tray menu on GUI thread if possible
                    try:
                        try:
                            enqueue_gui_call(update_tray_menu)
                        except Exception:
                            update_tray_menu()
                    except Exception:
                        pass
                except Exception as e:
                    print("Resume handler error:", e)
            last_time = now
            schedule.run_pending()
        except Exception as e:
            print("Scheduler loop error:", e)
        time.sleep(poll_interval)


def update_scheduled_tasks(settings):
    schedule.clear()
    try:
        # Use a short toast + countdown before applying the scheduled mode
        schedule.every().day.at(settings.get("day_start", "08:00")).do(lambda: schedule_apply_after_delay(10, 'day'))
        schedule.every().day.at(settings.get("day_end", "18:00")).do(lambda: schedule_apply_after_delay(10, 'night'))
    except Exception as e:
        print("Scheduling error:", e)


def start_system_tray():
    settings_local = load_settings()

    menu = Menu(
        MenuItem(tr('day_mode','Gündüz Modu'), lambda icon, item: set_brightness_contrast(settings_local.get("day_brightness", "100"), settings_local.get("day_contrast", "100")), checked=lambda item: is_day_mode()),
        MenuItem(tr('night_mode','Gece Modu'), lambda icon, item: set_brightness_contrast(settings_local.get("night_brightness", "50"), settings_local.get("night_contrast", "70")), checked=lambda item: is_night_mode()),
        MenuItem(tr('settings','Ayarlar'), lambda icon, item: open_settings_window()),
        MenuItem(tr('exit','Çıkış'), lambda icon, item: (icon.stop(), os._exit(0)))
    )

    # keep a persistent reference to the PIL image so it isn't garbage-collected
    global tray_icon, tray_image
    try:
        tray_image = create_image()
    except Exception:
        tray_image = None

    icon = Icon("lightguard", tray_image, menu=menu)
    # expose icon for shutdown handler
    tray_icon = icon
    # ensure menu reflects current_mode/time
    try:
        update_tray_menu()
    except Exception:
        pass

    try:
        time.sleep(1)
        try:
            # attempt to make icon visible and run; log exceptions for diagnostics
            try:
                icon.visible = True
            except Exception:
                pass
            icon.run()
        except Exception as e:
            logger.exception('Tray icon error:')
            print("Tray icon error:", e)
    except Exception as e:
        logger.exception('Tray startup failed:')
        print("Tray icon error:", e)


def shutdown(signum=None, frame=None):
    """Clean shutdown: stop tray icon, clear hotkeys and scheduled jobs."""
    print(tr('shutting_down','LightGuard kapatılıyor...'))
    try:
        schedule.clear()
    except Exception:
        pass
    try:
        keyboard.unhook_all()
    except Exception:
        try:
            keyboard.unhook_all_hotkeys()
        except Exception:
            pass
    try:
        if 'tray_icon' in globals() and tray_icon is not None:
            tray_icon.stop()
    except Exception:
        pass
    try:
        sys.exit(0)
    except SystemExit:
        os._exit(0)


def _power_wnd_proc(hwnd, msg, wparam, lparam):
    # Window procedure for power events
    try:
        if msg == win32con.WM_POWERBROADCAST:
            # PBT_APMRESUMESUSPEND = 7, PBT_APMRESUMEAUTOMATIC = 18
            if wparam in (win32con.PBT_APMRESUMESUSPEND, getattr(win32con, 'PBT_APMRESUMEAUTOMATIC', 18)):
                logger.info('Power event: resume detected via WM_POWERBROADCAST')
                try:
                    # Ensure GUI thread performs the apply to match manual tray behavior
                    def _on_resume():
                        try:
                            global current_mode
                            previous_mode = current_mode
                            current_mode = 'auto'
                        except Exception:
                            pass

                        def do_apply():
                            logger.info('Power event: do_apply started')
                            try:
                                update_scheduled_tasks(load_settings())
                            except Exception:
                                pass
                            try:
                                applied = apply_settings()
                                logger.info(f'Power event: apply_settings returned {applied}')
                            except Exception as e:
                                logger.exception('Power event apply error:')
                                applied = False
                            try:
                                # ensure tray update runs on GUI thread
                                try:
                                    enqueue_gui_call(update_tray_menu)
                                except Exception:
                                    try:
                                        update_tray_menu()
                                    except Exception:
                                        logger.exception('update_tray_menu failed')
                            except Exception:
                                pass

                        # if apply reported success, ensure persistence for a while
                        try:
                            if applied:
                                mode, tb, tc = get_profile_values()
                                logger.info(f'Power event: ensuring persistence for mode={mode} b={tb} c={tc}')
                                ok = ensure_persistence(tb, tc, timeout=40, poll=2.0, required_consecutive=3)
                                logger.info(f'Power event: ensure_persistence result={ok}')
                        except Exception:
                            logger.exception('Power event: ensure_persistence failed')


                        # Schedule a console countdown + apply after 30s
                        try:
                            schedule_apply_after_delay(10)
                            logger.info('Power event: scheduled apply with 30s countdown')
                            return
                        except Exception:
                            logger.exception('Power event: schedule_apply_after_delay failed')

                    try:
                        enqueue_gui_call(_on_resume)
                    except Exception:
                        # if enqueue fails, call _on_resume which will schedule appropriately
                        _on_resume()
                except Exception as e:
                    print('Power event handler error:', e)
    except Exception:
        pass
    return True


def start_power_event_listener():
    """Create a hidden window to listen for WM_POWERBROADCAST messages (Windows only).
    This allows the app to react immediately to actual resume events instead of relying on time-jump heuristics.
    """
    if not have_pywin32:
        print(tr('power_listener_disabled','pywin32 bulunamadı: güç olayı dinleyicisi devre dışı'))
        return

    try:
        # register window class
        wc = win32gui.WNDCLASS()
        hinst = wc.hInstance = win32api.GetModuleHandle(None)
        wc.lpszClassName = 'LightGuardPowerListener'
        wc.lpfnWndProc = _power_wnd_proc
        class_atom = win32gui.RegisterClass(wc)
        # create message-only window
        hwnd = win32gui.CreateWindowEx(0, class_atom, 'LightGuardPowerWindow', 0, 0, 0, 0, 0, 0, 0, hinst, None)
        print(tr('power_listener_started','Güç olayı dinleyicisi başlatıldı'))
        # message pump
        while True:
            win32gui.PumpWaitingMessages()
            time.sleep(0.1)
    except Exception as e:
        print('Power event listener failed:', e)


if __name__ == "__main__":
    setup_keyboard_shortcuts()
    print(tr('press_ctrl_alt_s','Ayarları açmak için Ctrl+Alt+S tuşuna basın.'))
    print(tr('press_ctrl_alt_a','Ayarları uygulamak için Ctrl+Alt+A tuşuna basın.'))

    # Start schedule runner in background
    schedule_thread = threading.Thread(target=schedule_runner, daemon=True)
    schedule_thread.start()

    # Update scheduled tasks initially
    try:
        update_scheduled_tasks(load_settings())
    except Exception:
        pass

    # Start system tray in main thread so icon is shown
    # register signal handlers for Ctrl+C
    try:
        signal.signal(signal.SIGINT, shutdown)
    except Exception:
        pass
    try:
        signal.signal(signal.SIGTERM, shutdown)
    except Exception:
        pass

    # Initialize GUI queue and root so all Tk operations run on the main thread.
    try:
        gui_queue = queue.Queue()
        gui_root = tk.Tk()
        # hide main root; we use Toplevel windows for dialogs
        try:
            gui_root.withdraw()
        except Exception:
            pass
        # initialize UI palette/styles after root exists
        try:
            init_ui_palette()
        except Exception:
            pass
        # start processing GUI queue
        try:
            gui_root.after(100, process_gui_queue)
        except Exception:
            pass
    except Exception as e:
        print("GUI initialization error:", e)

    # Start system tray in a background thread so the main thread can run Tk mainloop
    try:
        tray_thread = threading.Thread(target=start_system_tray, daemon=True)
        tray_thread.start()
    except Exception as e:
        print("Failed to start tray thread:", e)

    # Start power event listener if available (pywin32)
    try:
        if have_pywin32:
            power_thread = threading.Thread(target=start_power_event_listener, daemon=True)
            power_thread.start()
        else:
            print(tr('power_listener_disabled','pywin32 kurulu değil; Windows güç olayları dinleyicisi atlanıyor'))
    except Exception as e:
        print('Failed to start power event listener thread:', e)

    # Run the Tk mainloop on the main thread to avoid Tkinter "main thread" issues.
    try:
        gui_root.mainloop()
    except KeyboardInterrupt:
        shutdown()
    except Exception:
        # ensure clean shutdown on unexpected GUI errors
        try:
            shutdown()
        except Exception:
            pass