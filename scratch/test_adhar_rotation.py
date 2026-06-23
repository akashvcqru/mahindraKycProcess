import os
import sys
import fitz # PyMuPDF
import easyocr
from PIL import Image

sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')

def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    pdf_path = os.path.abspath(os.path.join(script_dir, "..", "documents", "SRaghul Selvam", "ADHAR-1781345999022.pdf"))
    
    print(f"Loading EasyOCR...")
    reader = easyocr.Reader(['en'], gpu=False)
    
    doc = fitz.open(pdf_path)
    page = doc.load_page(0)
    pix = page.get_pixmap(dpi=150)
    img_data = pix.tobytes("png")
    
    # Load into PIL Image
    import io
    base_image = Image.open(io.BytesIO(img_data))
    
    # Test rotations: 0, 90, 180, 270 degrees clockwise
    for angle in [0, 90, 180, 270]:
        print(f"\n--- Testing Clockwise Rotation: {angle} degrees ---")
        if angle == 0:
            rotated_img = base_image
        else:
            rotated_img = base_image.rotate(-angle, expand=True) # Pillow rotate uses counter-clockwise, so negative is clockwise
            
        # Convert PIL Image back to bytes
        img_byte_arr = io.BytesIO()
        rotated_img.save(img_byte_arr, format='PNG')
        img_bytes = img_byte_arr.getvalue()
        
        # OCR
        results = reader.readtext(img_bytes, detail=0)
        text = " ".join(results)
        print(f"Extracted Text: {text}")
        
        # Check if we can find typical Aadhaar markers
        markers = ["government", "india", "dob", "male", "female", "year of birth", "issue date"]
        found = [m for m in markers if m in text.lower()]
        print(f"Matched markers: {found}")

if __name__ == "__main__":
    main()
