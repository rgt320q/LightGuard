import importlib, time, queue
import tkinter as tk

# Import the app module
import main
importlib.reload(main)

# Ensure GUI root and queue exist
main.gui_queue = queue.Queue()
main.gui_root = tk.Tk()
# hide main root window
try:
    main.gui_root.withdraw()
except Exception:
    pass

# initialize palette/styles if needed
try:
    main.init_ui_palette()
except Exception:
    pass

# start processing GUI queue
try:
    main.gui_root.after(100, main.process_gui_queue)
except Exception:
    pass

print('TEST: scheduling toast for 7s')
main.schedule_apply_after_delay(7)

# keep the GUI responsive for a short while so toast can appear
end = time.time() + 12
try:
    while time.time() < end:
        try:
            main.gui_root.update()
        except Exception:
            pass
        time.sleep(0.03)
except KeyboardInterrupt:
    pass

print('TEST DONE')
try:
    main.gui_root.destroy()
except Exception:
    pass
