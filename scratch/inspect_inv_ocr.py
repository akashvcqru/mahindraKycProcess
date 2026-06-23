import sys
import os
import json
import logging

workspace_dir = r"C:\Users\admin\Desktop\robbinmahindra"
sys.path.append(workspace_dir)

import automate_login

logging.basicConfig(level=logging.INFO)

pdf_path = os.path.join(workspace_dir, "documents", "Bhuvana M", "INV-1782129306377.pdf")
text, is_digital = automate_login.extract_text_hybrid(pdf_path)

print("--- OCR TEXT ---")
print(text)
print("--- OPENAI CACHE CONTENT ---")
res = automate_login.OPENAI_CACHE.get(pdf_path)
print(json.dumps(res, indent=2) if res else "No cache entry found")
