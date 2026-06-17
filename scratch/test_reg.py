import winreg
import sys

# Avoid encoding issues on Windows
sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')

try:
    key_path = r"SOFTWARE\Policies\Microsoft\Edge"
    key = winreg.CreateKey(winreg.HKEY_CURRENT_USER, key_path)
    winreg.SetValueEx(key, "DownloadNotificationEnabled", 0, winreg.REG_DWORD, 0)
    winreg.CloseKey(key)
    print("Successfully set HKEY_CURRENT_USER\\SOFTWARE\\Policies\\Microsoft\\Edge\\DownloadNotificationEnabled = 0")
except Exception as e:
    print(f"Error setting registry: {e}")

# Verify it
try:
    key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"SOFTWARE\Policies\Microsoft\Edge")
    val, val_type = winreg.QueryValueEx(key, "DownloadNotificationEnabled")
    winreg.CloseKey(key)
    print(f"Verification: DownloadNotificationEnabled value is {val} (type: {val_type})")
except Exception as e:
    print(f"Error verifying registry: {e}")
