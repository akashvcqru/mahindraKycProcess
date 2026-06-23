import os
import sys
import logging
from playwright.sync_api import sync_playwright

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] %(levelname)s: %(message)s")

def main():
    p = sync_playwright().start()
    
    local_app_data = os.getenv("LOCALAPPDATA")
    user_data_path = os.path.join(local_app_data, r"Microsoft\Edge\User Data")
    
    logging.info("Launching Edge in persistent mode...")
    try:
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
        logging.error(f"Failed to launch Edge: {e}")
        p.stop()
        return

    try:
        print("\n=== Instructions ===")
        print("1. If not already there, navigate to the claims table.")
        print("2. Click the 'View' eye icon on the first claim row.")
        print("3. In the drawer, click the 'Supporting Document' tab.")
        print("4. Once the document cards are loaded on the screen, press Enter in this terminal.")
        input("\nPress Enter to dump the HTML of the cards...")

        # Locate the cards
        card_selector = "div.ant-card"
        cards = page.locator(card_selector)
        count = cards.count()
        logging.info(f"Found {count} cards in the DOM matching 'div.ant-card'.")

        scratch_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "scratch")
        os.makedirs(scratch_dir, exist_ok=True)
        out_path = os.path.join(scratch_dir, "cards_dump.html")

        with open(out_path, "w", encoding="utf-8") as f:
            f.write("<html><body>\n")
            for i in range(count):
                card = cards.nth(i)
                html = card.evaluate("el => el.outerHTML")
                f.write(f"<h2>Card {i+1}</h2>\n")
                f.write(html)
                f.write("<hr/>\n")
            f.write("</body></html>\n")

        logging.info(f"HTML of cards successfully written to: {out_path}")
        print("\nDump completed! You can close the browser or press Enter to close the script.")
        input()
    except Exception as err:
        logging.error(f"Error: {err}")
    finally:
        context.close()
        p.stop()

if __name__ == "__main__":
    main()
