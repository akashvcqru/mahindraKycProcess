import os
import fitz # PyMuPDF

def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    pdf_path = os.path.abspath(os.path.join(script_dir, "..", "documents", "SRaghul Selvam", "ADHAR-1781345999022.pdf"))
    out_png = os.path.abspath(os.path.join(script_dir, "adhar_page.png"))
    
    print(f"Opening PDF: {pdf_path}")
    doc = fitz.open(pdf_path)
    page = doc.load_page(0)
    print(f"Page size: {page.rect}")
    
    pix = page.get_pixmap(dpi=300) # render at 300 DPI for high quality
    pix.save(out_png)
    print(f"Saved page 1 to: {out_png}")

if __name__ == "__main__":
    main()
