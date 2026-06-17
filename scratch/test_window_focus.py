import ctypes
import time
import sys

# Avoid encoding issues on Windows
sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')

def press_escape_os():
    print("Simulating OS-level Escape keypress...")
    # VK_ESCAPE = 0x1B
    # Key down
    ctypes.windll.user32.keybd_event(0x1B, 0, 0, 0)
    time.sleep(0.05)
    # Key up
    ctypes.windll.user32.keybd_event(0x1B, 0, 2, 0)
    print("Escape keypress completed.")

def focus_edge():
    print("Searching for Microsoft Edge window...")
    # Edge uses Chrome_WidgetWin_1 class
    # Let's find window handle
    hwnd = ctypes.windll.user32.FindWindowW("Chrome_WidgetWin_1", None)
    if hwnd:
        print(f"Found Edge window handle: {hwnd}")
        # Bring to front
        ctypes.windll.user32.ShowWindow(hwnd, 9) # SW_RESTORE
        ctypes.windll.user32.SetForegroundWindow(hwnd)
        print("Brought Edge window to foreground.")
        return True
    else:
        print("Could not find Edge window using class Chrome_WidgetWin_1.")
        return False

# Test focus and keypress
if focus_edge():
    time.sleep(0.5)
    press_escape_os()
else:
    print("Test skipped because Edge window was not found.")
