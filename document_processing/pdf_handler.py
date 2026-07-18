import os
import base64
import io
import logging
from PIL import Image

def get_stitched_base64_document(file_path):
    """Converts a multi-page PDF or image file into a single vertically stitched optimized JPEG base64 string.
    
    Uses 300 DPI high-quality rendering via PyMuPDF (fitz) to prevent quality loss.
    """
    if not file_path or not os.path.exists(file_path):
        logging.warning(f"[PDF Handler] File not found: {file_path}")
        return None
    
    ext = os.path.splitext(file_path.lower())[1]
    images = []
    
    try:
        if ext == '.pdf':
            # Convert PDF pages to PIL Images at 300 DPI using PyMuPDF (fitz)
            import fitz
            doc = fitz.open(file_path)
            zoom = 300 / 72  # Convert standard 72 DPI to high-quality 300 DPI
            matrix = fitz.Matrix(zoom, zoom)
            
            for page_num in range(len(doc)):
                page = doc.load_page(page_num)
                pix = page.get_pixmap(matrix=matrix)
                img_data = pix.tobytes("png")
                img = Image.open(io.BytesIO(img_data))
                images.append(img)
            doc.close()
        elif ext in ['.png', '.jpg', '.jpeg', '.bmp']:
            # Already an image file
            img = Image.open(file_path)
            img.load()
            images.append(img)
        else:
            logging.warning(f"[PDF Handler] Unsupported file format: {ext}")
            return None
            
        if not images:
            return None
            
        # Stitch images vertically
        max_width = max(img.width for img in images)
        total_height = sum(img.height for img in images)
        
        # Create the master canvas (RGBA)
        stitched_image = Image.new("RGBA", (max_width, total_height), (255, 255, 255, 0))
        
        y_offset = 0
        for img in images:
            # Paste each page sequentially down the canvas
            stitched_image.paste(img, (0, y_offset))
            y_offset += img.height
            
        # Save stitched image to bytes buffer as high-quality JPEG
        buffered = io.BytesIO()
        if stitched_image.mode in ('RGBA', 'LA') or (stitched_image.mode == 'P' and 'transparency' in stitched_image.info):
            background = Image.new("RGB", stitched_image.size, (255, 255, 255))
            background.paste(stitched_image, mask=stitched_image.split()[3])  # Apply transparency mask
            stitched_image = background
        else:
            stitched_image = stitched_image.convert("RGB")
            
        stitched_image.save(buffered, format="JPEG", quality=85, optimize=True)
        img_str = base64.b64encode(buffered.getvalue()).decode("utf-8")
        
        logging.info(f"[PDF Handler] Successfully stitched document {os.path.basename(file_path)}: {len(images)} pages.")
        return img_str
        
    except Exception as e:
        logging.error(f"[PDF Handler] Error processing document {file_path}: {e}")
        return None
