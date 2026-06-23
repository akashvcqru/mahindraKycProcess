import os
import sys
import json
import logging

sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from automate_login import extract_details_via_openai

logging.basicConfig(level=logging.INFO)

pdf_path = r"c:\Users\admin\Desktop\robbinmahindra\documents\Vijesh N Saigal\INV-1782112143204.pdf"
print("Calling OpenAI Vision API for Invoice...")
res = extract_details_via_openai(pdf_path)
print(json.dumps(res, indent=2))
