import os
import shutil
import sys
import traceback
from playwright.sync_api import sync_playwright

def copy_profile():
    local_app_data = os.getenv("LOCALAPPDATA")
    src_user_data = os.path.join(local_app_data, r"Microsoft\Edge\User Data")
    dst_user_data = os.path.join(os.getcwd(), "Edge_Playwright_Profile")
    
    print(f"Copying from {src_user_data} to {dst_user_data}")
    
    os.makedirs(dst_user_data, exist_ok=True)
    
    # Copy Local State
    src_local_state = os.path.join(src_user_data, "Local State")
    if os.path.exists(src_local_state):
        shutil.copy2(src_local_state, os.path.join(dst_user_data, "Local State"))
        print("Copied Local State")
        
    # Copy Profile 3
    src_profile = os.path.join(src_user_data, "Profile 3")
    dst_profile = os.path.join(dst_user_data, "Profile 3")
    if os.path.exists(src_profile):
        if os.path.exists(dst_profile):
            shutil.rmtree(dst_profile, ignore_errors=True)
        try:
            shutil.copytree(src_profile, dst_profile, dirs_exist_ok=True)
            print("Copied Profile 3")
        except Exception as e:
            print(f"Error copying Profile 3: {e}")
            
    print("Launch Playwright...")
    try:
        with sync_playwright() as p:
            context = p.chromium.launch_persistent_context(
                user_data_dir=dst_user_data,
                channel="msedge",
                headless=False,
                args=[
                    "--profile-directory=Profile 3",
                    "--disable-blink-features=AutomationControlled",
                ],
                accept_downloads=True,
            )
            page = context.pages[0]
            page.goto("https://www.mahindradealerrise.com/", timeout=10000)
            print("Successfully launched and navigated!")
            context.close()
    except Exception as e:
        print(f"Playwright error: {e}")
        traceback.print_exc()

if __name__ == "__main__":
    copy_profile()
