import logging
import sys
import os

# Add parent directory to path so we can import automate_login
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import automate_login

logging.basicConfig(level=logging.INFO)

image_path = r"C:\Users\admin\Desktop\robbinmahindra\documents\GOUTAM PAUL\document_2.jpg"
if os.path.exists(image_path):
    print("Image file exists.")
    try:
        text, is_digital = automate_login.extract_text_hybrid(image_path)
        print(f"Extracted text: {text[:200]}")
        print(f"Is digital: {is_digital}")
    except Exception as e:
        print(f"Error occurred: {e}")
else:
    print(f"Image file does not exist: {image_path}")
