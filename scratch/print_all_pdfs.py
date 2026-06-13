import os
import glob
from pypdf import PdfReader

script_dir = os.path.dirname(os.path.abspath(__file__))
documents_dir = os.path.abspath(os.path.join(script_dir, "..", "documents"))

pdf_files = glob.glob(os.path.join(documents_dir, "**", "*.pdf"), recursive=True)
for p in pdf_files:
    rel = os.path.relpath(p, documents_dir)
    print(f"\n====================\nFILE: {rel}\n====================")
    try:
        reader = PdfReader(p)
        text = ""
        for page in reader.pages:
            t = page.extract_text()
            if t:
                text += t + "\n"
        print(text[:1000])
    except Exception as e:
        print(f"Error: {e}")
