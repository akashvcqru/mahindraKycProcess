import os
import json
import sys

# Avoid encoding issues on Windows
sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')

local_app_data = os.getenv("LOCALAPPDATA")
user_data_path = os.path.join(local_app_data, r"Microsoft\Edge\User Data")
prefs_path = os.path.join(user_data_path, "Default", "Preferences")

def recursive_search_all(d, path=""):
    results = {}
    if isinstance(d, dict):
        for k, v in d.items():
            new_path = f"{path}.{k}" if path else k
            lower_path = new_path.lower()
            if any(term in lower_path for term in ["download", "bubble", "popup", "flyout", "hub", "notification"]):
                if not isinstance(v, (dict, list)):
                    results[new_path] = v
            results.update(recursive_search_all(v, new_path))
    elif isinstance(d, list):
        for idx, item in enumerate(d):
            new_path = f"{path}[{idx}]"
            results.update(recursive_search_all(item, new_path))
    return results

if os.path.exists(prefs_path):
    try:
        with open(prefs_path, "r", encoding="utf-8") as f:
            prefs = json.load(f)
            
        found = recursive_search_all(prefs)
        print("Matching preference paths:")
        for k, v in sorted(found.items()):
            print(f"  {k}: {v}")
    except Exception as e:
        print(f"Error: {e}")
else:
    print("Preferences file does not exist.")
