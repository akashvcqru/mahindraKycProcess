import os
import json
import sys

# Avoid encoding issues on Windows
sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')

local_app_data = os.getenv("LOCALAPPDATA")
user_data_path = os.path.join(local_app_data, r"Microsoft\Edge\User Data")
prefs_path = os.path.join(user_data_path, "Default", "Preferences")

if os.path.exists(prefs_path):
    try:
        with open(prefs_path, "r", encoding="utf-8") as f:
            prefs = json.load(f)
            
        print("All keys under 'download':")
        download_prefs = prefs.get("download", {})
        for k, v in sorted(download_prefs.items()):
            if not isinstance(v, (dict, list)):
                print(f"  download.{k}: {v}")
            else:
                print(f"  download.{k}: {type(v)}")
                
        print("\nAll keys under 'download_bubble':")
        bubble_prefs = prefs.get("download_bubble", {})
        for k, v in sorted(bubble_prefs.items()):
            print(f"  download_bubble.{k}: {v}")
            
    except Exception as e:
        print(f"Error: {e}")
else:
    print("Preferences file does not exist.")
