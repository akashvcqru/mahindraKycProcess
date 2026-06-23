import os
import json
import sys

# Avoid encoding issues on Windows
sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')

local_app_data = os.getenv("LOCALAPPDATA")
user_data_path = os.path.join(local_app_data, r"Microsoft\Edge\User Data")
prefs_path = os.path.join(user_data_path, "Default", "Preferences")

print(f"Checking Preferences path: {prefs_path}")
if os.path.exists(prefs_path):
    print("Preferences file exists.")
    try:
        with open(prefs_path, "r", encoding="utf-8") as f:
            prefs = json.load(f)
            
        print("Checking download bubble preferences:")
        print(f"  download.prompt_for_download: {prefs.get('download', {}).get('prompt_for_download')}")
        print(f"  plugins.always_open_pdf_externally: {prefs.get('plugins', {}).get('always_open_pdf_externally')}")
        print(f"  download_bubble.partial_view_enabled: {prefs.get('download_bubble', {}).get('partial_view_enabled')}")
        print(f"  download.show_downloads_in_companion: {prefs.get('download', {}).get('show_downloads_in_companion')}")
        print(f"  download.show_downloads_hub: {prefs.get('download', {}).get('show_downloads_hub')}")
        print(f"  profile.default_content_settings.popups: {prefs.get('profile', {}).get('default_content_settings', {}).get('popups')}")
    except Exception as e:
        print(f"Error reading Preferences: {e}")
else:
    print("Preferences file does NOT exist yet or profile path is different.")
