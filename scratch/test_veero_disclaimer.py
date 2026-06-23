import os
import sys
import logging
import json

sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')

# Import the extract_disclaimer_spatial from automate_login.py
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from automate_login import extract_disclaimer_spatial, extract_text_hybrid

# Setup logging
logging.basicConfig(level=logging.INFO, format="[%(asctime)s] %(levelname)s: %(message)s")

pdf_path = r"C:\Users\admin\Desktop\robbinmahindra\documents\ABILASHGOWDA A\DISC -1781516436736.pdf"
customer_name = "ABILASHGOWDA A"

print("Running extract_disclaimer_spatial...")
res = extract_disclaimer_spatial(pdf_path, customer_name)
print("\n=== EXTRACTION RESULT ===")
print(json.dumps(res, indent=2))
print("=========================")
