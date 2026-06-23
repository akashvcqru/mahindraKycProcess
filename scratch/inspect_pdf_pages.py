import fitz  # PyMuPDF

pdf_path = r"c:\Users\admin\Desktop\robbinmahindra\documents\PRAVIN\PRAVIN  LEDGER-1782131597951.pdf"
doc = fitz.open(pdf_path)
print("Number of pages:", len(doc))
for i in range(len(doc)):
    page = doc.load_page(i)
    text = page.get_text()
    print(f"\n--- Page {i+1} Text ---")
    print(repr(text))
