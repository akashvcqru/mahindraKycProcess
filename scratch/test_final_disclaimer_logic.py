import sys
import os
import glob

# Add workspace to path
sys.path.append(os.path.abspath("."))
from automate_login import extract_text_hybrid, verify_documents

# Mock claim choice and other elements
claim_choice = "1"

print("--- Testing disclaimers using actual automate_login.py functions ---")
pdf_files = glob.glob("documents/**/*.pdf", recursive=True)
for p in pdf_files:
    filename = os.path.basename(p).upper()
    if "DIS" in filename or "DISCLAIMER" in filename:
        print(f"\nProcessing: {p}")
        text, is_dig = extract_text_hybrid(p)
        print(f"  - Extracted as Digital: {is_dig}")
        
        text_norm = text.upper()
        old_keywords = ["SOLEMNLY", "AFFIRM", "DECLARE"]
        has_old_format = any(kw in text_norm for kw in old_keywords)
        
        new_keywords = [
            "CUSTOMER DISCLAIMER",
            "CONFIRM",
            "WELCOME" if "WELCOME" in text_norm else "WELCOMC",
            "DEALER" if "DEALER" in text_norm else "DEATER",
            "VEHICLE" if "VEHICLE" in text_norm else "VEHIC",
            "CHASSIS" if "CHASSIS" in text_norm else "GHASSIS",
            "ENGINE" if "ENGINE" in text_norm else "ENGIN",
            "INVOICE"
        ]
        matching_new_kws = sum(1 for kw in new_keywords if kw in text_norm)
        print(f"  - Old format keywords present: {has_old_format}")
        print(f"  - New format keywords count: {matching_new_kws}/8")
        
        if has_old_format or matching_new_kws < 5:
            print("  - VERDICT: HOLD (Format mismatch)")
        else:
            print("  - VERDICT: PASS")
