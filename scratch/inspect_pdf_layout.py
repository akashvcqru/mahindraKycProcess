import fitz

pdf_path = r"c:\Users\admin\Desktop\robbinmahindra\DISC -1781516436736.pdf"
doc = fitz.open(pdf_path)
print(f"Total pages: {len(doc)}")
for i, page in enumerate(doc):
    print(f"\n--- Page {i+1} Text blocks ---")
    blocks = page.get_text("blocks")
    for block in blocks:
        # block format: (x0, y0, x1, y1, "text", block_no, block_type)
        print(f"[{block[0]:.1f}, {block[1]:.1f}, {block[2]:.1f}, {block[3]:.1f}] -> {repr(block[4])}")
