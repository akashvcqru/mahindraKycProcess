import os
import sys
import logging
from getpass import getpass
from playwright.sync_api import sync_playwright

# Configure logging to console
logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)s: %(message)s",
    datefmt="%H:%M:%S"
)

# Target URL
TARGET_URL = "https://www.mahindradealerrise.com/"

class KeepBrowserOpenException(Exception):
    """Custom exception raised when the user wants to exit but keep the browser window open."""
    pass

def wait_and_click(page, selector, timeout=20000):
    page.wait_for_selector(selector, state="visible", timeout=timeout)
    page.click(selector)

def wait_and_fill(page, selector, text, timeout=20000):
    page.wait_for_selector(selector, state="visible", timeout=timeout)
    page.locator(selector).clear()
    page.fill(selector, text)

def execute_step_with_interaction(page, step_func, step_name):
    """Executes a step function in Playwright. If it fails, prompts the user to terminate, keep open, or retry."""
    while True:
        try:
            return step_func()
        except Exception as e:
            logging.warning(f"Stuck or failed at step: '{step_name}'")
            print(f"Details: {e}")
            while True:
                print("\nChoose an option:")
                print("  y : Terminate browser and close script")
                print("  n : Do NOT terminate browser, wait/pause (allows manual action & retry)")
                print("  r : Reload / retry this step immediately")
                print("  q : Quit script but leave the browser open")
                
                choice = input("Selection (y/n/r/q): ").strip().lower()
                if choice == 'y':
                    logging.info("Terminating browser and exiting.")
                    sys.exit(1)
                elif choice == 'n':
                    print("\n[Info] Browser kept open. Script is waiting...")
                    print("You can manually perform any required actions in the browser window now.")
                    input("Press Enter here when you are ready to retry/reload the step...")
                    break  # Break inner loop, retry outer loop
                elif choice == 'r':
                    logging.info(f"Reloading/Retrying step: '{step_name}'...")
                    break  # Break inner loop, retry outer loop
                elif choice == 'q':
                    logging.info("Exiting script. Browser remains open as requested.")
                    # Force exit python process without cleanup to keep browser open
                    os._exit(0)
                else:
                    print("Invalid option. Please enter 'y', 'n', 'r', or 'q'.")

def main():
    print("=== Mahindra Rise Edge Login Automation (Playwright Migration) ===")
    
    # 1. Mode Choice
    print("\n1. Use existing logged-in session (Already Login)")
    print("2. Perform a fresh login process (New Login)")
    choice = input("Select an option (1/2): ").strip()
    
    if choice not in ["1", "2"]:
        logging.error("Invalid option selected. Exiting.")
        sys.exit(1)
        
    use_existing = (choice == "1")
    
    # Initialize Playwright Context
    p = sync_playwright().start()
    
    browser = None
    context = None
    page = None
    
    try:
        if use_existing:
            # Default Microsoft Edge User Data path on Windows
            local_app_data = os.getenv("LOCALAPPDATA")
            user_data_path = os.path.join(local_app_data, r"Microsoft\Edge\User Data")
            
            logging.info(f"Launching Edge with profile path: {user_data_path}")
            logging.warning("Ensure all other Microsoft Edge instances are closed before proceeding, otherwise connection will fail.")
            
            context = p.chromium.launch_persistent_context(
                user_data_dir=user_data_path,
                channel="msedge",
                headless=False,
                args=[
                    "--profile-directory=Default",
                    "--disable-blink-features=AutomationControlled"
                ]
            )
            page = context.pages[0]
        else:
            logging.info("Launching a fresh Microsoft Edge session...")
            browser = p.chromium.launch(
                channel="msedge",
                headless=False,
                args=["--disable-blink-features=AutomationControlled"]
            )
            context = browser.new_context()
            page = context.new_page()

    except Exception as e:
        logging.critical(f"Failed to launch Microsoft Edge: {e}")
        logging.critical("Please ensure that Microsoft Edge is installed and closed (if using option 1).")
        p.stop()
        sys.exit(1)
        
    should_quit = True
    try:
        # Navigation step
        logging.info(f"Navigating to {TARGET_URL}...")
        execute_step_with_interaction(
            page,
            lambda: page.goto(TARGET_URL),
            "Navigate to Target URL"
        )
        
        if use_existing:
            # Click "M&M User Login" and finish
            execute_step_with_interaction(
                page,
                lambda: wait_and_click(page, "#login_from > div:nth-child(5) > div:nth-child(1) > div > a"),
                "Click M&M User Login button"
            )
            logging.info("Successfully clicked 'M&M User Login' using existing profile session.")
            input("\nPress Enter here when you are done to close the browser...")
            return

        # --- Fresh Login Flow (New Login) ---
        
        # Get credentials securely
        email = input("Enter your User ID (e.g. 50016105@mahindra.com): ").strip()
        if not email:
            email = "50016105@mahindra.com"
            logging.info(f"Using default email: {email}")
            
        password = getpass("Enter your Password: ")
        
        # 1. Click "M&M User Login"
        execute_step_with_interaction(
            page,
            lambda: wait_and_click(page, "#login_from > div:nth-child(5) > div:nth-child(1) > div > a"),
            "Click M&M User Login button"
        )
        
        # 2. Enter email ID
        execute_step_with_interaction(
            page,
            lambda: wait_and_fill(page, "#i0116", email),
            "Enter email ID in Microsoft login"
        )
        
        # 3. Click Next button
        execute_step_with_interaction(
            page,
            lambda: wait_and_click(page, "#idSIButton9"),
            "Click Next button"
        )
        
        # 4. Enter password
        execute_step_with_interaction(
            page,
            lambda: wait_and_fill(page, "#i0118", password),
            "Enter password in Microsoft login"
        )
        
        # 5. Click Sign In button
        execute_step_with_interaction(
            page,
            lambda: wait_and_click(page, "#idSIButton9"),
            "Click Sign In button"
        )
        
        # 6. Handle MFA / Proof options popup (Select Text Option)
        def select_mfa_text_option():
            page.wait_for_selector("#idDiv_SAOTCS_Proofs", state="visible", timeout=20000)
            wait_and_click(page, "#idDiv_SAOTCS_Proofs > div:nth-child(1) > div > div > div.table-cell.text-left.content")
        
        execute_step_with_interaction(
            page,
            select_mfa_text_option,
            "Select MFA Text/SMS option"
        )
        
        # 7. Enter OTP
        def enter_otp_flow():
            page.wait_for_selector("#idTxtBx_SAOTCC_OTC", state="visible", timeout=20000)
            otp = input("\nPlease enter the OTP sent to your text/number: ").strip()
            wait_and_fill(page, "#idTxtBx_SAOTCC_OTC", otp)
            wait_and_click(page, "#idSubmit_SAOTCC_Continue")
            
        execute_step_with_interaction(
            page,
            enter_otp_flow,
            "Enter and submit OTP"
        )
        
        # 8. Handle "Stay signed in?" prompt
        def stay_signed_in_flow():
            page.wait_for_selector("#lightbox", state="visible", timeout=20000)
            wait_and_click(page, "#idSIButton9")
            
        execute_step_with_interaction(
            page,
            stay_signed_in_flow,
            "Click Yes to Stay Signed In"
        )
        
        logging.info("Login automation process completed successfully!")
        input("\nPress Enter here to close the browser...")

    except KeepBrowserOpenException:
        logging.info("Exiting script. Browser remains open as requested.")
        should_quit = False
    except Exception as e:
        logging.error(f"An unexpected error occurred during automation: {e}")
    finally:
        if should_quit:
            if context is not None:
                context.close()
            if browser is not None:
                browser.close()
            p.stop()

if __name__ == "__main__":
    main()
