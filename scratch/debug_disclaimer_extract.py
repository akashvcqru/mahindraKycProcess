import os
import sys
import logging

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from automate_login import extract_disclaimer_spatial

logging.basicConfig(level=logging.INFO)

pdf_path = r"c:\Users\admin\Desktop\robbinmahindra\documents\ABILASHGOWDA A\DISC -1781516436736.pdf"
res = extract_disclaimer_spatial(pdf_path, "ABILASHGOWDA A")
print("\nFINAL EXTRACTED DATA:")
for k, v in res.items():
    print(f"  {k}: {v}")
