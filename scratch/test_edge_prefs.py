from playwright.sync_api import sync_playwright
import os

def test_launch():
    local_app_data = os.getenv("LOCALAPPDATA")
    user_data_path = os.path.join(local_app_data, r"Microsoft\Edge\User Data")
    
    p = sync_playwright().start()
    try:
        # Define preferences to disable prompts and force PDFs to download
        prefs = {
            "download.prompt_for_download": False,
            "download.directory_upgrade": True,
            "plugins.always_open_pdf_externally": True,
            "profile.default_content_settings.popups": 0
        }
        
        print("Launching Edge with custom preferences...")
        context = p.chromium.launch_persistent_context(
            user_data_dir=user_data_path,
            channel="msedge",
            headless=False,
            args=[
                "--profile-directory=Default",
                "--disable-blink-features=AutomationControlled"
            ],
            accept_downloads=True,
            no_viewport=True,
            prefs=prefs
        )
        print("Launched successfully!")
        context.close()
    except Exception as e:
        print(f"Error launching: {e}")
    finally:
        p.stop()

if __name__ == "__main__":
    test_launch()
