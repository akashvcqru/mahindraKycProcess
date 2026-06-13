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

def load_scheme_data():
    """Loads and parses the scheme data from scheme_data.txt."""
    schemes = {
        "welcome": {},
        "scrappage": {}
    }
    
    scheme_file = "scheme_data.txt"
    if not os.path.exists(scheme_file):
        logging.warning(f"Scheme file '{scheme_file}' not found. Using empty data.")
        return schemes
        
    try:
        current_section = None
        with open(scheme_file, "r") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                if "WELCOME BONUS" in line:
                    current_section = "welcome"
                    continue
                elif "SCRAPPAGE SCHEME" in line:
                    current_section = "scrappage"
                    continue
                    
                if current_section == "welcome":
                    if "Brand:" in line:
                        brand = line.split("Brand:")[1].strip().upper()
                    elif "Credit note" in line:
                        val = line.split(":")[-1].strip()
                        amount = float(''.join(c for c in val if c.isdigit() or c == '.'))
                        schemes["welcome"][brand] = amount
                elif current_section == "scrappage":
                    if "|" in line and "Brand" not in line:
                        parts = [p.strip() for p in line.split("|") if p.strip()]
                        if len(parts) >= 5:
                            # The last 4 columns are numeric: Contribution (A), Contribution (B), Total, Credit Note
                            # All elements before those last 4 are brand strings
                            brand_parts = parts[:-4]
                            credit_note_str = parts[-1]
                            try:
                                amount = float(''.join(c for c in credit_note_str if c.isdigit() or c == '.'))
                                for brand_part in brand_parts:
                                    # Split brands by '/'
                                    sub_brands = [b.strip().upper() for b in brand_part.split("/") if b.strip()]
                                    for b in sub_brands:
                                        schemes["scrappage"][b] = amount
                            except Exception:
                                pass
    except Exception as e:
        logging.error(f"Error reading/parsing scheme_data.txt: {e}")
        
    return schemes

def find_matching_schemes(brand_name, schemes):
    """Looks up all matching expected credit notes in both scrappage and welcome schemes."""
    brand_name = brand_name.strip().upper()
    matches = {}
    
    # 1. Check Welcome Scheme
    welcome_match = None
    if brand_name in schemes["welcome"]:
        welcome_match = schemes["welcome"][brand_name]
    else:
        # Check substring match
        for key, val in schemes["welcome"].items():
            if key in brand_name or brand_name in key:
                welcome_match = val
                break
    if welcome_match is not None:
        matches["Welcome"] = welcome_match
        
    # 2. Check Scrappage Scheme
    scrappage_match = None
    if brand_name in schemes["scrappage"]:
        scrappage_match = schemes["scrappage"][brand_name]
    else:
        # Check substring match
        for key, val in schemes["scrappage"].items():
            if key in brand_name or brand_name in key:
                scrappage_match = val
                break
    if scrappage_match is not None:
        matches["Scrappage"] = scrappage_match
        
    return matches

def parse_drawer_table_general(page, required_keys=None, exclude_keys=None, min_non_empty=1, timeout=15000):
    """Parses a table inside the Ant Design Drawer dynamically, waiting for elements to load."""
    table_selector = "div.ant-drawer-body table"
    page.wait_for_selector(table_selector, state="visible", timeout=timeout)
    
    start_time = time.time()
    temp_data = {}
    while time.time() - start_time < timeout:
        rows = page.locator(f"{table_selector} > tbody > tr")
        row_count = rows.count()
        
        temp_data = {}
        i = 0
        while i < row_count:
            row_headers = rows.nth(i).locator("th")
            header_count = row_headers.count()
            
            if header_count > 0:
                if i + 1 < row_count:
                    row_values = rows.nth(i + 1).locator("td")
                    value_count = row_values.count()
                    
                    for col_idx in range(min(header_count, value_count)):
                        hdr = row_headers.nth(col_idx).inner_text().strip()
                        val = row_values.nth(col_idx).inner_text().strip()
                        if hdr:
                            temp_data[hdr] = val
                i += 2
            else:
                i += 1
                
        # Wait until we have enough non-empty values
        non_empty = sum(1 for k, v in temp_data.items() if v.strip() != "-" and v.strip() != "")
        
        # Check required keys if provided
        keys_satisfied = True
        if required_keys:
            keys_satisfied = any(temp_data.get(k, "-").strip() != "-" for k in required_keys)
            
        # Check exclude keys if provided (if any exclude key has a non-dash value, we are still showing old tab data)
        exclude_satisfied = True
        if exclude_keys:
            exclude_satisfied = all(temp_data.get(k, "-").strip() == "-" for k in exclude_keys)
            
        if non_empty >= min_non_empty and keys_satisfied and exclude_satisfied:
            return temp_data
            
        page.wait_for_timeout(500)
        
    return temp_data

def parse_drawer_details_table(page):
    """Parses the Ant Design Drawer table mapping headers to values dynamically, waiting for data to populate."""
    return parse_drawer_table_general(page, required_keys=["Chassis No", "Invoice No"], min_non_empty=3)

def select_drawer_timeline_tab(page, tab_name):
    """Clicks on a specific timeline item tab in the details drawer sidebar."""
    tab_locator = page.locator("div.ant-drawer-body").get_by_text(tab_name).first
    tab_locator.wait_for(state="visible", timeout=20000)
    
    logging.info(f"Clicking on details drawer tab: '{tab_name}'")
    tab_locator.scroll_into_view_if_needed()
    tab_locator.click()
    
    # Give the page 1.5 seconds to finish rendering/updating the pane content
    page.wait_for_timeout(1500)

def download_supporting_documents(page, context, customer_name):
    """Downloads all supporting documents in the current pane to documents/<customer_name>/."""
    def get_extension_from_headers(headers, default=".pdf"):
        content_type = headers.get("content-type", "").lower()
        if "pdf" in content_type:
            return ".pdf"
        elif "png" in content_type:
            return ".png"
        elif "jpeg" in content_type or "jpg" in content_type:
            return ".jpg"
        elif "gif" in content_type:
            return ".gif"
        elif "webp" in content_type:
            return ".webp"
        return default

    # Sanitize customer name for folder path
    safe_customer_name = "".join(c for c in customer_name if c.isalnum() or c in (" ", "_", "-")).strip()
    if not safe_customer_name:
        safe_customer_name = "Unknown_Customer"
        
    script_dir = os.path.dirname(os.path.abspath(__file__))
    target_dir = os.path.join(script_dir, "documents", safe_customer_name)
    os.makedirs(target_dir, exist_ok=True)
    logging.info(f"Target directory for documents: {target_dir}")
    
    # Target data-testid="downloadBtn" directly inside the supporting documents view
    button_selector = '[data-testid="downloadBtn"], svg[data-testid="downloadBtn"]'
    try:
        page.wait_for_selector(button_selector, state="visible", timeout=15000)
    except Exception:
        logging.warning("No download buttons (data-testid='downloadBtn') found/loaded within 15 seconds. Skipping.")
        return
        
    buttons = page.locator(button_selector)
    button_count = buttons.count()
    logging.info(f"Found {button_count} document download buttons in Supporting Documents.")
    
    for i in range(button_count):
        btn = buttons.nth(i)
        
        # Get the closest parent card ancestor to correctly extract the header title
        card = btn.locator("xpath=./ancestor::div[contains(@class, 'ant-card') or contains(@class, 'app_viewDocumentStrip')][1]").first
        
        title = f"document_{i+1}"
        try:
            title_el = card.locator(".ant-card-head-title, .ant-card-head")
            if title_el.count() > 0:
                title_text = title_el.first.inner_text().split("\n")[0].strip()
                if title_text:
                    title = "".join(c for c in title_text if c.isalnum() or c in (" ", "_", "-")).strip()
        except Exception as title_err:
            logging.debug(f"Failed to get card title: {title_err}")
            
        logging.info(f"Downloading supporting document {i+1}/{button_count}: {title}...")
        
        # We register event listeners for both page (new tab) and download (direct file stream) events
        event_result = {
            "download": None,
            "new_page": None,
            "response": None
        }
        
        def on_page(p):
            event_result["new_page"] = p
            
            # Watch for responses inside this new tab
            def on_response(res):
                try:
                    if res.request.resource_type in ["document", "image"] or res.url == p.url:
                        if event_result["response"] is None:
                            event_result["response"] = res
                except Exception:
                    pass
            p.on("response", on_response)
            
            # Watch for downloads inside this new tab
            p.on("download", lambda d: on_download(d))
            
        def on_download(d):
            event_result["download"] = d
            
        context.on("page", on_page)
        page.on("download", on_download)
        
        success = False
        try:
            # Click the button (try normal click, fall back to dispatching raw click event if obstructed)
            try:
                btn.click(timeout=3000)
            except Exception:
                btn.dispatch_event("click")
                
            # Poll up to 10 seconds for either event to fire
            start_time = time.time()
            page_open_time = None
            while time.time() - start_time < 10.0:
                if event_result["download"] is not None:
                    break
                if event_result["new_page"] is not None:
                    if page_open_time is None:
                        page_open_time = time.time()
                    # Wait up to 3 seconds after page opens to see if a download event starts
                    if time.time() - page_open_time > 3.0:
                        break
                page.wait_for_timeout(200)
                
            if event_result["download"] is not None:
                download = event_result["download"]
                suggested = download.suggested_filename
                ext = ".pdf"
                if "." in suggested:
                    ext = "." + suggested.split(".")[-1]
                target_path = os.path.join(target_dir, f"{title}{ext}")
                download.save_as(target_path)
                logging.info(f"Downloaded: {target_path}")
                success = True
            elif event_result["response"] is not None:
                response = event_result["response"]
                body = response.body()
                ext = get_extension_from_headers(response.headers)
                target_path = os.path.join(target_dir, f"{title}{ext}")
                with open(target_path, "wb") as f:
                    f.write(body)
                logging.info(f"Downloaded from response: {target_path}")
                success = True
            elif event_result["new_page"] is not None:
                new_page = event_result["new_page"]
                new_page.wait_for_load_state("load", timeout=5000)
                url = new_page.url
                
                # Check for images or fallback
                ext = ".pdf"
                if any(img_ext in url.lower() for img_ext in [".png", ".jpg", ".jpeg", ".gif"]):
                    for img_ext in [".png", ".jpg", ".jpeg", ".gif"]:
                        if img_ext in url.lower():
                            ext = img_ext
                            break
                            
                target_path = os.path.join(target_dir, f"{title}{ext}")
                
                # Try fallback fetch
                pdf_bytes = new_page.evaluate("""
                    async (url) => {
                        const response = await fetch(url);
                        const buffer = await response.arrayBuffer();
                        return Array.from(new Uint8Array(buffer));
                    }
                """, url)
                
                with open(target_path, "wb") as f:
                    f.write(bytes(pdf_bytes))
                logging.info(f"Downloaded via fallback fetch: {target_path}")
                success = True
            else:
                logging.warning(f"Timeout waiting for download/page events for card '{title}'")
        except Exception as err:
            logging.error(f"Error handling download for card '{title}': {err}")
        finally:
            # Clean up the new page if it was opened
            if event_result["new_page"] is not None:
                try:
                    event_result["new_page"].close()
                except Exception:
                    pass
            # Unregister listeners to prevent double-triggering or memory leaks
            try:
                context.remove_listener("page", on_page)
            except Exception:
                pass
            try:
                page.remove_listener("download", on_download)
            except Exception:
                pass
                
        if not success:
            logging.error(f"Could not download supporting document: {title}")

def click_row_action_button(page):
    """Robustly clicks the Action / Eye button in the first row of the claims table."""
    cell_selector = "#root > div > div > div > div > div > div > div > div > div > div > main > div:nth-child(4) > div > div > div.app_mainDataTable__4u2RN > div > div > div > div > div > div > table > tbody > tr:nth-child(1) > td:nth-child(9)"
    page.wait_for_selector(cell_selector, state="visible", timeout=20000)
    
    # Try finding and clicking the svg or button tag directly to trigger the click handler
    svg_locator = page.locator(f"{cell_selector} button > svg, {cell_selector} svg")
    if svg_locator.count() > 0:
        svg_locator.first.click()
        return
        
    button_locator = page.locator(f"{cell_selector} button")
    if button_locator.count() > 0:
        button_locator.first.click()
        return
        
    div_locator = page.locator(f"{cell_selector} div > div")
    if div_locator.count() > 0:
        div_locator.first.click()
        return
        
    # Fallback to direct cell click
    page.click(cell_selector)

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
        base_docs_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "documents")
        os.makedirs(base_docs_dir, exist_ok=True)
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
        
        # Select sub-menu item based on choice
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
        
        # Select Zone
        zone_container = f"{MODAL_CONTENT} form > div:nth-child(1) > div:nth-child(1) > div > div"
        execute_step_with_interaction(
            page,
            lambda: select_antd_dropdown_option(page, get_antd_select_trigger(page, zone_container, "Zone"), select_first=True, field_name="Zone"),
            "Select Zone (Single option)"
        )
        
        # Select Area Office
        office_container = f"{MODAL_CONTENT} form > div:nth-child(1) > div:nth-child(2) > div > div"
        execute_step_with_interaction(
            page,
            lambda: select_antd_dropdown_option(page, get_antd_select_trigger(page, office_container, "Area Office"), ask_user=True, field_name="Area Office"),
            "Select Area Office"
        )
        
        # Select Dealer Name
        dealer_container = f"{MODAL_CONTENT} form > div:nth-child(1) > div:nth-child(3) > div > div"
        execute_step_with_interaction(
            page,
            lambda: select_antd_dropdown_option(page, get_antd_select_trigger(page, dealer_container, "Dealer Name"), option_text="All", field_name="Dealer Name"),
            "Select Dealer Name (All)"
        )
        
        # Select Location Name
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
            calculated_from = first_of_month
            calculated_to = today_str
            logging.info(f"Loyalty Claims selected. Automatically using date range: {calculated_from} to {calculated_to}")
        else:
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
                
        try:
            day_from = int(calculated_from.split('/')[0])
            day_to = int(calculated_to.split('/')[0])
        except Exception:
            day_from = 1
            day_to = now.day

        # Fill From Date (Using precise ID: #fromDate)
        from_container = f"{MODAL_CONTENT} form > div:nth-child(2) > div:nth-child(1) > div > div"
        execute_step_with_interaction(
            page,
            lambda: fill_antd_date_robust(page, "#fromDate", from_container, calculated_from, day_from),
            "Fill Claim From Date"
        )
        
        # Fill To Date (Using precise ID: #toDate)
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
        
        # Apply filters automatically
        apply_button = f"{MODAL_CONTENT} form > div:nth-child(3) > div > div > span:nth-child(2) > button"
        execute_step_with_interaction(
            page,
            lambda: wait_and_click(page, apply_button),
            "Click Apply button"
        )
        logging.info("Filters applied successfully!")
        
        # Wait for search API/table loading to start and fully complete
        logging.info("Waiting for data table loading/refresh to complete...")
        page.wait_for_timeout(3000)  # Wait 3 seconds for load states
        try:
            # Wait for any Ant Design load indicators to hide
            page.wait_for_selector(".ant-spin-spinning", state="hidden", timeout=15000)
        except Exception:
            pass
        page.wait_for_timeout(1000)  # General stability delay

        # --- PROCESS FIRST ROW CLAIM DETAILS ---
        logging.info("Locating data table...")
        table_container_selector = "div.app_mainDataTable__4u2RN"
        page.wait_for_selector(table_container_selector, state="visible", timeout=20000)
        
        # Load schemes from local text file
        schemes = load_scheme_data()
        
        # Check if table has rows
        rows = page.locator(f"{table_container_selector} table tbody tr")
        row_count = rows.count()
        if row_count == 0:
            logging.info("No claims found in the results table.")
            input("\nPress Enter here to close the browser...")
            return
            
        logging.info("First row available. Triggering 'View' action...")
        
        # Execute click on the action eye button
        execute_step_with_interaction(
            page,
            lambda: click_row_action_button(page),
            "Click view action (eye icon) on the first row"
        )
        
        # Wait for Details Drawer to slide out
        execute_step_with_interaction(
            page,
            lambda: page.wait_for_selector("div.ant-drawer-content-wrapper", state="visible", timeout=20000),
            "Wait for Details Drawer to open"
        )
        
        # Parse claim details table inside drawer
        logging.info("Parsing claim details metadata table...")
        claim_details = parse_drawer_details_table(page)
        
        # Print parsed data in console
        print("\n=== Extracted Claim Details ===")
        for key, val in claim_details.items():
            print(f"  {key} : {val}")
            
        # Validate: extract "New Vehicle Model Group" and "Approved Total Amount"
        model_group = None
        approval_amount = None
        
        for k, v in claim_details.items():
            norm_k = k.lower()
            if "new vehicle model group" in norm_k or "new vehical model group" in norm_k:
                model_group = v
            elif "approved total amount" in norm_k or "approval total amount" in norm_k or "approved amount" in norm_k:
                # Prioritize approved total amount over approved dealer amount
                if "dealer" not in norm_k:
                    approval_amount = v
                
        # Enable ANSI escape code processing on Windows
        if os.name == 'nt':
            os.system('')

        GREEN_TEXT = "\033[92m"
        RED_TEXT = "\033[91m"
        RESET_TEXT = "\033[0m"

        print("\n=== Scheme Validation Status ===")
        if model_group and approval_amount:
            print(f"  Model Group from Claim: {model_group}")
            print(f"  Approval Amount from Claim: {approval_amount}")
            
            # Find matching values in scheme_data.txt (could be in Welcome, Scrappage, or both)
            matched_schemes = find_matching_schemes(model_group, schemes)
            if matched_schemes:
                print("  Expected Credit Note Amounts (excluding GST) from scheme_data.txt:")
                for s_type, s_amount in matched_schemes.items():
                    print(f"    - {s_type} Scheme: {s_amount}")
                
                try:
                    # Parse claim's approval amount as float
                    clean_val_str = ''.join(c for c in approval_amount if c.isdigit() or c == '.')
                    actual_val = float(clean_val_str)
                    
                    # Check if actual_val matches any of the matched schemes
                    matched_any = False
                    for s_type, s_amount in matched_schemes.items():
                        diff = abs(actual_val - s_amount)
                        if diff < 1.0:
                            print(f"{GREEN_TEXT}  --> Result: MATCH (Approval amount {actual_val} matches {model_group} {s_type} Scheme {s_amount} within rounding tolerance of 1.0; difference is {diff:.2f}) [FINE]{RESET_TEXT}")
                            matched_any = True
                            break
                            
                    if not matched_any:
                        expected_desc = " or ".join(f"{v} ({k})" for k, v in matched_schemes.items())
                        print(f"{RED_TEXT}  --> Result: MISMATCH (Expected {expected_desc}, got {actual_val}) [FAILED]{RESET_TEXT}")
                except Exception as parse_err:
                    print(f"{RED_TEXT}  --> Result: UNABLE TO COMPARE (Error parsing approval amount '{approval_amount}': {parse_err}) [FAILED]{RESET_TEXT}")
            else:
                print(f"{RED_TEXT}  --> Result: Brand '{model_group}' not found in scheme_data.txt mappings. [FAILED]{RESET_TEXT}")
        else:
            reasons = []
            if not model_group:
                reasons.append("Missing 'New vehicle Model Group' key/value")
            if not approval_amount:
                reasons.append("Missing 'Approved Total Amount' key/value")
            print(f"{RED_TEXT}  --> Result: Missing required validation keys in claim details table. ({', '.join(reasons)}) [FAILED]{RESET_TEXT}")
            print(f"      (Keys found: {list(claim_details.keys())})")
            
        # --- NEW SECTION: Fetch Old Vehicle Details ---
        try:
            logging.info("Switching to 'Old Vehicle Details' tab...")
            select_drawer_timeline_tab(page, "Old Vehicle Details")
            
            logging.info("Parsing old vehicle details table...")
            old_vehicle_details = parse_drawer_table_general(page, exclude_keys=["Invoice No", "New vehicle Model Group"], min_non_empty=1)
            
            print("\n=== Extracted Old Vehicle Details ===")
            if old_vehicle_details:
                for key, val in old_vehicle_details.items():
                    print(f"  {key} : {val}")
            else:
                print("  No details found or table was empty.")
        except Exception as old_vehicle_err:
            logging.warning(f"Failed to fetch or parse Old Vehicle Details: {old_vehicle_err}")

        # --- NEW SECTION: Fetch Supporting Documents ---
        try:
            logging.info("Switching to 'Supporting Documents' tab...")
            select_drawer_timeline_tab(page, "Supporting Document")
            
            logging.info("Downloading supporting documents...")
            customer_name = claim_details.get("Customer Name", "Unknown_Customer")
            download_supporting_documents(page, context, customer_name)
        except Exception as docs_err:
            logging.warning(f"Failed to fetch or download Supporting Documents: {docs_err}")

        # Wait for user input to close details
        input("\nPress Enter to close details and close the browser...")
        
        # Close Drawer
        close_btn = page.locator("button.ant-drawer-close, .ant-drawer-close-x, .ant-drawer-header button").first
        close_btn.click()
        page.wait_for_selector("div.ant-drawer-content-wrapper", state="hidden", timeout=10000)
        logging.info("Drawer closed.")

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
