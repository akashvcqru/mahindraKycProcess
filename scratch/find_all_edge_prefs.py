import os
import json
import sys

# Avoid encoding issues on Windows
sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')

local_app_data = os.getenv("LOCALAPPDATA")
user_data_path = os.path.join(local_app_data, r"Microsoft\Edge\User Data")
prefs_path = os.path.join(user_data_path, "Default", "Preferences")

def recursive_search(d, path=""):
    results = {}
    if isinstance(d, dict):
        for k, v in d.items():
            new_path = f"{path}.{k}" if path else k
            # Check if key matches interesting terms
            lower_k = k.lower()
            if any(term in lower_k for term in ["download", "bubble", "popup", "flyout", "hub", "notification"]):
                results[new_path] = v
            # Recurse
            results.update(recursive_search(v, new_path))
    elif isinstance(d, list):
        for idx, item in enumerate(d):
            new_path = f"{path}[{idx}]"
            results.update(recursive_search(item, new_path))
    return results

print(f"Checking Preferences path: {prefs_path}")
if os.path.exists(prefs_path):
    try:
        with open(prefs_path, "r", encoding="utf-8") as f:
            prefs = json.load(f)
            
        print("Searching for download/bubble/popup/hub keys:")
        found = recursive_search(prefs)
        for k, v in sorted(found.items()):
            # Only print values that are not huge dictionaries or lists
            if not isinstance(v, (dict, list)):
                print(f"  {k}: {v}")
    except Exception as e:
        print(f"Error reading Preferences: {e}")
else:
    print("Preferences file does NOT exist.")
