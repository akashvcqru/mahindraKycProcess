import fitz
import os
import sys

sys.stdout.reconfigure(encoding='utf-8')

dir_path = r"c:\Users\admin\Desktop\robbinmahindra\documents\LALU PRASAD RANA"
for filename in os.listdir(dir_path):
    if filename.endswith(".pdf"):
        path = os.path.join(dir_path, filename)
        doc = fitz.open(path)
        text = ""
        for page in doc:
            t = page.get_text()
            if t:
                text += t + "\n"
        print(f"\n==========================================")
        print(f"FILE: {filename}")
        print(f"==========================================")
        lines = [line.strip() for line in text.split("\n") if line.strip()]
        for line in lines[:50]:  # print first 50 lines
            print(line)
