import os
import sys
import logging

sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')

# Import the classify_and_extract function from automate_login.py
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from automate_login import classify_and_extract, extract_text_hybrid

# Setup logging
logging.basicConfig(level=logging.INFO, format="[%(asctime)s] %(levelname)s: %(message)s")

pdf_path = r"C:\Users\admin\Desktop\robbinmahindra\documents\ABILASHGOWDA A\AADHAR-1781516436638.pdf"
customer_name = "ABILASHGOWDA A"

print("Extracting Aadhaar text...")
text, is_digital = extract_text_hybrid(pdf_path)
print(f"Raw Text Sample: {repr(text[:200])}")

print("\nClassifying and extracting...")
res = classify_and_extract(pdf_path, text, customer_name)
print(f"Result: {res}")
