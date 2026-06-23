import fitz
import easyocr
import sys

sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')

pdf_path = r"c:\Users\admin\Desktop\robbinmahindra\documents\HARISH M B\HARISH M B DGLV  (2)-1781972860016.pdf"
doc = fitz.open(pdf_path)
reader = easyocr.Reader(['en'], gpu=False)

for page_num in range(len(doc)):
    page = doc.load_page(page_num)
    pix = page.get_pixmap(dpi=150)
    png_bytes = pix.tobytes("png")
    results = reader.readtext(png_bytes, detail=0)
    print("Page", page_num + 1)
    print(" ".join(results))
