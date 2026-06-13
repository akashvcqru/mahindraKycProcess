import fitz
import easyocr
import sys

sys.stdout.reconfigure(encoding='utf-8')

reader = easyocr.Reader(['en'], gpu=False)
doc = fitz.open(r"c:\Users\admin\Desktop\robbinmahindra\documents\SRaghul Selvam\VAHAN-1781345998669.pdf")
for i, page in enumerate(doc):
    pix = page.get_pixmap(dpi=150)
    png_bytes = pix.tobytes("png")
    text = " ".join(reader.readtext(png_bytes, detail=0))
    print(f"PAGE {i+1}: {text}")
