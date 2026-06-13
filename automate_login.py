import os
import sys
import time
import logging
import subprocess
from datetime import datetime, timedelta
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

def check_and_close_running_edge():
    """Detects if Microsoft Edge is running and prompts the user to close it to release profile locks."""
    try:
        # Check if msedge.exe is running on Windows
        res = subprocess.run(["tasklist", "/FI", "IMAGENAME eq msedge.exe"], capture_output=True, text=True)
        if "msedge.exe" in res.stdout:
            logging.warning("Microsoft Edge is currently running.")
            print("\n[Action Required] To access your profile, Microsoft Edge must be closed.")
            choice = input("Would you like to automatically close all running Microsoft Edge windows? (y/n): ").strip().lower()
            if choice == 'y':
                logging.info("Closing Microsoft Edge...")
                subprocess.run(["taskkill", "/F", "/IM", "msedge.exe"], capture_output=True)
                time.sleep(2)  # Give Windows a moment to release file locks
                logging.info("Edge windows closed successfully.")
            else:
                print("Please close Microsoft Edge manually, then press Enter to continue...")
                input()
    except Exception as e:
        logging.warning(f"Could not check/kill running Edge instances: {e}")

def wait_and_click(page, selector, timeout=20000):
    page.wait_for_selector(selector, state="visible", timeout=timeout)
    page.click(selector)

def wait_and_fill(page, selector, text, timeout=20000):
    page.wait_for_selector(selector, state="visible", timeout=timeout)
    page.locator(selector).clear()
    page.fill(selector, text)

def get_antd_select_trigger(page, container_selector, label_text):
    """Robustly retrieves the select trigger element inside a container, with label fallback."""
    # Method 1: Check label-based form item
    try:
        label_locator = page.locator(f'div.ant-modal-content form .ant-form-item:has(label:has-text("{label_text}")) .ant-select-selector')
        if label_locator.count() > 0:
            return label_locator.first
    except Exception:
        pass
        
    try:
        label_locator_alt = page.locator(f'div.ant-modal-content form .ant-form-item:has(label:has-text("{label_text}")) .ant-select-selection-item')
        if label_locator_alt.count() > 0:
            return label_locator_alt.first
    except Exception:
        pass

    # Method 2: Index-based container fallback with multiple class trials
    fallback_selector = (
        f"{container_selector} .ant-select-selector, "
        f"{container_selector} .ant-select-selection-item, "
        f"{container_selector} .ant-select"
    )
    return page.locator(fallback_selector).first

def select_antd_dropdown_option(page, trigger_element_or_selector, option_text=None, select_first=False, ask_user=False, field_name=""):
    """Clicks a dropdown selector, waits for options list, and selects one."""
    if isinstance(trigger_element_or_selector, str):
        page.wait_for_selector(trigger_element_or_selector, state="visible", timeout=20000)
        page.click(trigger_element_or_selector)
    else:
        # It's a locator object
        trigger_element_or_selector.wait_for(state="visible", timeout=20000)
        trigger_element_or_selector.click()
    
    # Wait for the Ant Design dropdown overlay to appear
    dropdown_selector = "div.ant-select-dropdown:not(.ant-select-dropdown-hidden)"
    page.wait_for_selector(dropdown_selector, state="visible", timeout=20000)
    
    # Brief sleep to ensure dynamic contents are populated
    page.wait_for_timeout(1000)
    
    option_items = page.locator(f"{dropdown_selector} .ant-select-item-option")
    count = option_items.count()
    if count == 0:
        raise Exception(f"No options found in the dropdown for field: {field_name}")
        
    options_data = []
    for i in range(count):
        opt = option_items.nth(i)
        text = opt.inner_text().strip()
        options_data.append((text, opt))
        
    if select_first:
        logging.info(f"Selecting first option for '{field_name}': {options_data[0][0]}")
        options_data[0][1].click()
        return options_data[0][0]
        
    if ask_user:
        print(f"\nAvailable options for {field_name}:")
        for idx, (text, _) in enumerate(options_data):
            print(f"  {idx + 1} : {text}")
            
        while True:
            try:
                choice = input(f"Select a number for {field_name}: ").strip()
                choice_idx = int(choice) - 1
                if 0 <= choice_idx < len(options_data):
                    target_text, target_opt = options_data[choice_idx]
                    logging.info(f"User selected: {target_text}")
                    target_opt.click()
                    return target_text
                else:
                    print("Invalid number. Try again.")
            except ValueError:
                print("Please enter a valid number.")
                
    if option_text:
        # Find option containing option_text
        for text, opt in options_data:
            if option_text.lower() in text.lower():
                logging.info(f"Selecting option for '{field_name}': {text}")
                opt.click()
                return text
        logging.warning(f"Option containing '{option_text}' not found for '{field_name}'. Clicking first option.")
        options_data[0][1].click()
        return options_data[0][0]

    # Default fallback
    options_data[0][1].click()
    return options_data[0][0]

def fill_antd_date_robust(page, select_id, fallback_container_selector, date_str, target_day):
    """Fills a date input field by direct ID/typing, with fallback to calendar popup selection."""
    try:
        # Method 1: Try direct ID typing
        page.wait_for_selector(select_id, state="visible", timeout=5000)
        page.click(select_id)
        page.locator(select_id).press("Control+A")
        page.locator(select_id).press("Backspace")
        page.locator(select_id).fill(date_str)
        page.locator(select_id).press("Enter")
        page.wait_for_timeout(500)
        logging.info(f"Filled date {date_str} in selector {select_id} via typing.")
        return
    except Exception as e:
        logging.info(f"Direct date typing failed or timed out for {select_id}: {e}. Trying calendar popup...")

    # Method 2: Click the date picker wrapper container to open the calendar overlay
    picker_wrapper = (
        f"{fallback_container_selector} > div.ant-col.ant-form-item-control.css-1442l13 > div > div > div > div, "
        f"{fallback_container_selector} .ant-picker, "
        f"{fallback_container_selector}"
    )
    page.wait_for_selector(picker_wrapper, state="visible", timeout=10000)
    page.click(picker_wrapper)
    
    # Wait for the active calendar overlay to display
    dropdown_selector = "div.ant-picker-dropdown:not(.ant-picker-dropdown-hidden)"
    page.wait_for_selector(dropdown_selector, state="visible", timeout=10000)
    page.wait_for_timeout(500)
    
    # In Ant Design, current month visible days have the class td.ant-picker-cell-in-view
    day_cells = page.locator(f"{dropdown_selector} td.ant-picker-cell-in-view .ant-picker-cell-inner")
    count = day_cells.count()
    for i in range(count):
        cell = day_cells.nth(i)
        if cell.inner_text().strip() == str(target_day):
            cell.click()
            # Wait for dropdown to close
            page.wait_for_selector(dropdown_selector, state="hidden", timeout=10000)
            logging.info(f"Selected day {target_day} from calendar for selector {select_id}.")
            return
            
    raise Exception(f"Failed to set date {date_str} for {select_id} using both typing and calendar selector.")

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
                    os._exit(0)
                else:
                    print("Invalid option. Please enter 'y', 'n', 'r', or 'q'.")

def main():
    print("=== Mahindra Rise Edge Login Automation ===")
    
    # 1. Mode Choice
    print("\n1. Use existing logged-in session (Already Login)")
    print("2. Perform a fresh login process (New Login)")
    choice = input("Select an option (1/2): ").strip()
    
    if choice not in ["1", "2"]:
        logging.error("Invalid option selected. Exiting.")
        sys.exit(1)
        
    use_existing = (choice == "1")
    
    # Always check and release profile lock, since both options use the same profile directory
    check_and_close_running_edge()
    
    # Initialize Playwright Context
    p = sync_playwright().start()
    
    context = None
    page = None
    
    # Default Microsoft Edge User Data path on Windows
    local_app_data = os.getenv("LOCALAPPDATA")
    user_data_path = os.path.join(local_app_data, r"Microsoft\Edge\User Data")
    
    try:
        # Both modes launch in your persistent Default profile directory
        logging.info(f"Launching Edge with profile path: {user_data_path}")
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

    except Exception as e:
        logging.critical(f"Failed to launch Microsoft Edge: {e}")
        logging.critical("Ensure all Edge windows are fully closed to release profile locks.")
        try:
            p.stop()
        except Exception:
            pass
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
        
        # Wait and check if browser automatically redirected to dashboard
        logging.info("Checking login state...")
        is_already_logged_in = False
        for _ in range(10):  # Check every 500ms for up to 5 seconds
            if "/dashboard" in page.url:
                is_already_logged_in = True
                break
            page.wait_for_timeout(500)
            
        current_url = page.url
        logging.info(f"Current page URL: {current_url}")
        
        # If already on the dashboard, skip all login steps entirely
        if is_already_logged_in or "/dashboard" in current_url:
            logging.info("Already logged in! Automatically bypassed login steps and navigated to dashboard.")
        else:
            # We are not logged in yet. Check and click M&M User Login
            def check_and_click_login():
                if "/dashboard" in page.url:
                    return True
                
                # Check for M&M User Login button visibility and click it
                btn_selector = "#login_from > div:nth-child(5) > div:nth-child(1) > div > a"
                try:
                    page.wait_for_selector(btn_selector, state="visible", timeout=5000)
                    page.click(btn_selector)
                    return False
                except Exception:
                    if "/dashboard" in page.url:
                        return True
                    raise  # Propagate error to trigger retry menu
                    
            is_redirected_to_dashboard = execute_step_with_interaction(
                page,
                lambda: check_and_click_login(),
                "Click M&M User Login button"
            )
            
            # If we clicked the button and didn't auto-bypass:
            if not is_redirected_to_dashboard:
                if use_existing:
                    logging.info("Using existing logged-in session. Bypassing credentials input. Waiting for dashboard redirect...")
                    execute_step_with_interaction(
                        page,
                        lambda: page.wait_for_url("**/dashboard", timeout=30000),
                        "Wait for dashboard auto-redirect"
                    )
                else:
                    # --- Fresh Login Flow (New Login) ---
                    
                    # Get credentials securely
                    email = input("Enter your User ID (e.g. 50016105@mahindra.com): ").strip()
                    if not email:
                        email = "50016105@mahindra.com"
                        logging.info(f"Using default email: {email}")
                    
                    password = getpass("Enter your Password: ")
                    
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
                        enter_otp_flow,
                        "Enter and submit OTP"
                    )
                    
                    # 8. Handle "Stay signed in?" prompt
                    def stay_signed_in_flow():
                        page.wait_for_selector("#lightbox", state="visible", timeout=20000)
                        wait_and_click(page, "#idSIButton9")
                        
                    execute_step_with_interaction(
                        stay_signed_in_flow,
                        "Click Yes to Stay Signed In"
                    )
                    
                    logging.info("Login automation completed successfully! Session saved.")

        # --- AFTER LOGIN FLOW ---
        
        # 1. Ask user for Claim Type
        print("\nSelect Claim Type to proceed:")
        print("1. Loyalty Claims")
        print("2. Exchange Claim")
        claim_choice = input("Select option (1/2): ").strip()
        while claim_choice not in ["1", "2"]:
            print("Invalid selection. Please enter 1 or 2.")
            claim_choice = input("Select option (1/2): ").strip()
            
        # 2. Navigate Left Side Menu
        # Click Sales
        execute_step_with_interaction(
            page,
            lambda: wait_and_click(page, "#root > div > div > div > div > div > div > div > div > div > aside > div > ul > li:nth-child(4) > div > span > a"),
            "Click Sales menu"
        )
        
        # Hover/Click Claims under Sales popup
        def hover_claims():
            claims_selector = 'ul[id*="-Sales-popup"] > li > div > span > a'
            page.wait_for_selector(claims_selector, state="visible", timeout=20000)
            page.hover(claims_selector)
            page.click(claims_selector)
            page.wait_for_timeout(500)
        execute_step_with_interaction(page, hover_claims, "Hover and click Claims sub-menu")
        
        # Hover/Click Exchange Claim under CLAIM popup
        def hover_exchange_claim():
            exchange_selector = 'ul[id*="-CLAIM-popup"] > li > div > span > a'
            page.wait_for_selector(exchange_selector, state="visible", timeout=20000)
            page.hover(exchange_selector)
            page.click(exchange_selector)
            page.wait_for_timeout(500)
        execute_step_with_interaction(page, hover_exchange_claim, "Hover and click Exchange Claim sub-menu")
        
        # Select sub-menu item based on choice (using text-based search for robustness)
        if claim_choice == "1":
            execute_step_with_interaction(
                page,
                lambda: wait_and_click(page, 'ul[id*="-SACT-22-popup"] a:has-text("Loyalty")'),
                "Click Loyalty Claims from popup menu"
            )
        else:
            execute_step_with_interaction(
                page,
                lambda: wait_and_click(page, 'ul[id*="-SACT-22-popup"] a:has-text("Exchange")'),
                "Click Exchange Claim from popup menu"
            )
            
        # 3. Click Advance Filter button
        execute_step_with_interaction(
            page,
            lambda: wait_and_click(page, 'button:has-text("Advance Filter")'),
            "Click Advance Filter button"
        )
        
        # 4. Handle Modal Dialog inputs
        execute_step_with_interaction(
            page,
            lambda: page.wait_for_selector("div.ant-modal-content", state="visible", timeout=20000),
            "Wait for Advance Filter popup modal"
        )
        
        MODAL_CONTENT = "div.ant-modal-content"
        
        # Select Zone (Always select first/single option)
        zone_container = f"{MODAL_CONTENT} form > div:nth-child(1) > div:nth-child(1) > div > div"
        execute_step_with_interaction(
            page,
            lambda: select_antd_dropdown_option(page, get_antd_select_trigger(page, zone_container, "Zone"), select_first=True, field_name="Zone"),
            "Select Zone (Single option)"
        )
        
        # Select Area Office (Show options and ask user)
        office_container = f"{MODAL_CONTENT} form > div:nth-child(1) > div:nth-child(2) > div > div"
        execute_step_with_interaction(
            page,
            lambda: select_antd_dropdown_option(page, get_antd_select_trigger(page, office_container, "Area Office"), ask_user=True, field_name="Area Office"),
            "Select Area Office"
        )
        
        # Select Dealer Name (Always select All)
        dealer_container = f"{MODAL_CONTENT} form > div:nth-child(1) > div:nth-child(3) > div > div"
        execute_step_with_interaction(
            page,
            lambda: select_antd_dropdown_option(page, get_antd_select_trigger(page, dealer_container, "Dealer Name"), option_text="All", field_name="Dealer Name"),
            "Select Dealer Name (All)"
        )
        
        # Select Location Name (Always select All)
        location_container = f"{MODAL_CONTENT} form > div:nth-child(1) > div:nth-child(4) > div > div"
        execute_step_with_interaction(
            page,
            lambda: select_antd_dropdown_option(page, get_antd_select_trigger(page, location_container, "Location Name"), option_text="All", field_name="Location Name"),
            "Select Location Name (All)"
        )
        
        # 5. Handle Date Selections
        now = datetime.now()
        first_of_month = now.replace(day=1).strftime("%d/%m/%Y")
        today_str = now.strftime("%d/%m/%Y")
        
        if claim_choice == "1":
            # Loyalty claims: Current month (1st day of month to today)
            calculated_from = first_of_month
            calculated_to = today_str
        else:
            # Exchange claims: 3 months back
            three_months_ago = now - timedelta(days=90)
            calculated_from = three_months_ago.replace(day=1).strftime("%d/%m/%Y")
            calculated_to = today_str
            
        print(f"\nCalculated Date Range:")
        print(f"  Claim From Date: {calculated_from}")
        print(f"  Claim To Date  : {calculated_to}")
        
        custom_confirm = input("Press Enter to use these dates, or type 'c' to enter custom dates: ").strip().lower()
        if custom_confirm == 'c':
            user_from = input(f"Enter Claim From Date (DD/MM/YYYY) [{calculated_from}]: ").strip()
            user_to = input(f"Enter Claim To Date (DD/MM/YYYY) [{calculated_to}]: ").strip()
            if user_from:
                calculated_from = user_from
            if user_to:
                calculated_to = user_to
                
        # Parse day numbers to feed into calendar click fallbacks
        try:
            day_from = int(calculated_from.split('/')[0])
            day_to = int(calculated_to.split('/')[0])
        except Exception:
            day_from = 1
            day_to = now.day

        # Fill From Date (Try ID typing first, then click calendar selector wrapper fallback)
        from_container = f"{MODAL_CONTENT} form > div:nth-child(2) > div:nth-child(1) > div > div"
        execute_step_with_interaction(
            page,
            lambda: fill_antd_date_robust(page, "#fromDate", from_container, calculated_from, day_from),
            "Fill Claim From Date"
        )
        
        # Fill To Date (Try ID typing first, then click calendar selector wrapper fallback)
        to_container = f"{MODAL_CONTENT} form > div:nth-child(2) > div:nth-child(2) > div > div"
        execute_step_with_interaction(
            page,
            lambda: fill_antd_date_robust(page, "#toDate", to_container, calculated_to, day_to),
            "Fill Claim To Date"
        )
        
        # Select Claim Status (Always select "Pending with SSKM")
        status_container = f"{MODAL_CONTENT} form > div:nth-child(2) > div:nth-child(3) > div > div"
        execute_step_with_interaction(
            page,
            lambda: select_antd_dropdown_option(page, get_antd_select_trigger(page, status_container, "Claim Status"), option_text="Pending with SSKM", field_name="Claim Status"),
            "Select Claim Status (Pending with SSKM)"
        )
        
        # Confirm Apply
        confirm_apply = input("\nConfirm applying these filter settings? (y/n): ").strip().lower()
        if confirm_apply == 'y':
            apply_button = f"{MODAL_CONTENT} form > div:nth-child(3) > div > div > span:nth-child(2) > button"
            execute_step_with_interaction(
                page,
                lambda: wait_and_click(page, apply_button),
                "Click Apply button"
            )
            logging.info("Filters applied successfully!")
        else:
            logging.info("Filter application cancelled by user.")

        input("\nPress Enter here to close the browser...")

    except KeepBrowserOpenException:
        logging.info("Exiting script. Browser remains open as requested.")
        should_quit = False
    except Exception as e:
        logging.error(f"An unexpected error occurred during automation: {e}")
    finally:
        if should_quit:
            # Safely close elements to prevent tracebacks if they were closed manually by the user
            try:
                if context is not None:
                    context.close()
            except Exception:
                pass
            try:
                p.stop()
            except Exception:
                pass

if __name__ == "__main__":
    main()
