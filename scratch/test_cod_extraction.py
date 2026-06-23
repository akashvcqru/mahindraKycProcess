import sys
import os

# Adjust path to import from workspace
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from automate_login import extract_text_hybrid, classify_and_extract

pdf_path = r"c:\Users\admin\Desktop\robbinmahindra\documents\HARISH M B\EOD-1781972860272.pdf"
print("Extracting...")
text, is_digital = extract_text_hybrid(pdf_path)
print(f"Is Digital: {is_digital}")
print("--- Text ---")
print(text)
print("--- Classification & Extraction ---")
res = classify_and_extract(pdf_path, text, "HARISH M B")
print(res)
