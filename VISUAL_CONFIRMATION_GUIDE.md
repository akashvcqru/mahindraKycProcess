# Visual Confirmation Feature - Implementation Guide

## 🎯 Goal
Add visual confirmation to the UI showing cropped images of:
- Dealer stamps/seals
- Customer signatures
- Dealer signatures  
- Invoice numbers
- Chassis numbers
- Any other extracted text fields

This allows you to **visually verify** what the AI detected without opening the original document.

---

## 📋 Implementation Plan

### Step 1: Modify OpenAI Extraction to Capture Bounding Boxes

**File**: `automate_login.py`  
**Function**: `extract_details_via_openai()`

#### 1.1 Update the Prompt to Request Bounding Boxes

Add this to the prompt (around line 2083-2141):

```python
prompt_text = """
... (existing prompt) ...

IMPORTANT: For each extracted field, also provide the bounding box coordinates where you found the information in the image. Return coordinates as [x_min, y_min, x_max, y_max] in pixels.

Return JSON in this format:
{
  "document_type": "",
  "customer_name": "",
  "invoice_number": "",
  ... (other fields) ...
  
  "bounding_boxes": {
    "customer_name": [x1, y1, x2, y2],
    "invoice_number": [x1, y1, x2, y2],
    "chassis_number": [x1, y1, x2, y2],
    "seal_stamp_dealer_name": [x1, y1, x2, y2],
    "customer_signature": [x1, y1, x2, y2],
    "dealer_signature": [x1, y1, x2, y2]
  }
}

Note: Bounding boxes should be in the format [left, top, right, bottom] relative to the image dimensions.
"""
```

#### 1.2 Add Function to Crop Images Based on Bounding Boxes

Add this new function after `extract_details_via_openai()`:

```python
def extract_visual_confirmations(pdf_path, extracted_data, base64_images):
    """
    Crop regions from the original document based on bounding boxes
    and save them as base64 images for visual confirmation.
    
    Returns: dict with field names as keys and cropped image data
    """
    import base64
    import io
    from PIL import Image
    
    visual_extractions = {}
    
    # Get bounding boxes from extraction result
    bounding_boxes = extracted_data.get("bounding_boxes", {})
    
    if not bounding_boxes or not base64_images:
        return visual_extractions
    
    try:
        # Decode the first page image (most extractions are from page 1)
        image_bytes = base64.b64decode(base64_images[0])
        image = Image.open(io.BytesIO(image_bytes))
        img_width, img_height = image.size
        
        # Process each field with bounding box
        for field_name, bbox in bounding_boxes.items():
            if not bbox or len(bbox) != 4:
                continue
            
            # Extract coordinates
            x1, y1, x2, y2 = bbox
            
            # Validate coordinates
            if x1 >= x2 or y1 >= y2:
                logging.warning(f"Invalid bbox for {field_name}: {bbox}")
                continue
            
            # Ensure coordinates are within image bounds
            x1 = max(0, min(x1, img_width))
            x2 = max(0, min(x2, img_width))
            y1 = max(0, min(y1, img_height))
            y2 = max(0, min(y2, img_height))
            
            # Add small padding (5% of width/height)
            padding_x = int((x2 - x1) * 0.05)
            padding_y = int((y2 - y1) * 0.05)
            
            x1 = max(0, x1 - padding_x)
            y1 = max(0, y1 - padding_y)
            x2 = min(img_width, x2 + padding_x)
            y2 = min(img_height, y2 + padding_y)
            
            # Crop the region
            cropped = image.crop((x1, y1, x2, y2))
            
            # Convert to base64
            buffered = io.BytesIO()
            cropped.save(buffered, format="PNG")
            img_base64 = base64.b64encode(buffered.getvalue()).decode('utf-8')
            
            # Get the extracted value and confidence
            field_value = extracted_data.get(field_name, "")
            confidence = extracted_data.get("confidence_score", 0)
            
            # Store visual extraction data
            visual_extractions[field_name] = {
                "value": field_value,
                "confidence": confidence,
                "bbox": bbox,
                "image_base64": img_base64
            }
            
            logging.info(f"Extracted visual confirmation for {field_name}")
        
        return visual_extractions
    
    except Exception as e:
        logging.error(f"Error extracting visual confirmations: {e}")
        return visual_extractions
```

#### 1.3 Integrate Visual Extraction into Main Flow

Modify the `extract_details_via_openai()` function to call the new function:

```python
def extract_details_via_openai(pdf_path, base64_images=None):
    # ... (existing code) ...
    
    # After successful extraction (around line 2250)
    if extracted_data:
        # Add visual confirmations
        visual_data = extract_visual_confirmations(
            pdf_path, 
            extracted_data, 
            base64_images
        )
        extracted_data["visual_extractions"] = visual_data
        
        logging.info(
            f"Successfully extracted {doc_type} data with {len(visual_data)} visual confirmations"
        )
        return extracted_data
```

---

### Step 2: Enhance the UI to Display Visual Confirmations

**File**: `app_ui.py`

#### 2.1 Add Visual Confirmation Panel to Layout

Replace or modify the `create_layout()` method around line 150-377:

```python
def create_layout(self):
    # ... (existing code for main container) ...
    
    # Change the main content area to use PanedWindow for resizable panels
    self.main_paned = ttk.PanedWindow(self.main_frame, orient=tk.HORIZONTAL)
    self.main_paned.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
    
    # LEFT PANEL: Claims List (20%)
    left_panel = ttk.Frame(self.main_paned, style="Card.TFrame", width=280)
    self.main_paned.add(left_panel, weight=2)
    
    # ... (existing claims list code) ...
    
    # CENTER PANEL: Document Viewer + Details (50%)
    center_panel = ttk.Frame(self.main_paned, style="Card.TFrame")
    self.main_paned.add(center_panel, weight=5)
    
    # ... (existing document viewer code) ...
    
    # RIGHT PANEL: Visual Confirmations (30%) - NEW!
    right_panel = ttk.Frame(self.main_paned, style="Card.TFrame", width=400)
    self.main_paned.add(right_panel, weight=3)
    
    # Visual Confirmations Header
    visual_header = tk.Frame(right_panel, bg=CARD_BG_COLOR)
    visual_header.pack(fill=tk.X, padx=10, pady=(10, 5))
    
    tk.Label(visual_header,
             text="🔍 Visual Confirmations",
             font=("Segoe UI", 12, "bold"),
             fg=TEXT_COLOR,
             bg=CARD_BG_COLOR).pack(side=tk.LEFT)
    
    # Scrollable frame for visual items
    visual_scroll_frame = tk.Frame(right_panel, bg=CARD_BG_COLOR)
    visual_scroll_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
    
    visual_canvas = tk.Canvas(visual_scroll_frame,
                              bg=BG_COLOR,
                              highlightthickness=0)
    visual_scrollbar = ttk.Scrollbar(visual_scroll_frame,
                                     orient=tk.VERTICAL,
                                     command=visual_canvas.yview)
    
    self.visual_frame = tk.Frame(visual_canvas, bg=BG_COLOR)
    
    self.visual_frame.bind(
        "<Configure>",
        lambda e: visual_canvas.configure(scrollregion=visual_canvas.bbox("all"))
    )
    
    visual_canvas.create_window((0, 0), window=self.visual_frame, anchor="nw")
    visual_canvas.configure(yscrollcommand=visual_scrollbar.set)
    
    visual_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    visual_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
    
    # Mouse wheel scrolling
    def on_mousewheel(event):
        visual_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
    visual_canvas.bind_all("<MouseWheel>", on_mousewheel)
    
    # Placeholder
    self.visual_placeholder = tk.Label(self.visual_frame,
                                       text="👁️ Visual extractions will\nappear here",
                                       font=("Segoe UI", 10),
                                       fg=TEXT_LIGHT_COLOR,
                                       bg=BG_COLOR)
    self.visual_placeholder.pack(pady=40)
    
    # Store PhotoImage references to prevent garbage collection
    self.extraction_images = []
```

#### 2.2 Add Method to Display Visual Confirmations

Add this new method to the `AppUI` class:

```python
def load_visual_confirmations(self, visual_data):
    """
    Display visual confirmations with cropped images.
    
    Args:
        visual_data: dict of {field_name: {value, confidence, bbox, image_base64}}
    """
    # Clear existing widgets
    for widget in self.visual_frame.winfo_children():
        widget.destroy()
    
    # Clear PhotoImage references
    self.extraction_images = []
    
    if not visual_data:
        # Show placeholder
        tk.Label(self.visual_frame,
                 text="👁️ No visual extractions\navailable",
                 font=("Segoe UI", 10),
                 fg=TEXT_LIGHT_COLOR,
                 bg=BG_COLOR).pack(pady=40)
        return
    
    # Define display order and labels
    field_display = {
        "seal_stamp_dealer_name": "🏢 Dealer Stamp/Seal",
        "customer_signature": "✍️ Customer Signature",
        "dealer_signature": "✍️ Dealer Signature",
        "invoice_number": "📄 Invoice Number",
        "chassis_number": "🚗 Chassis Number",
        "registration_number": "🚙 Registration Number",
        "invoice_date": "📅 Invoice Date",
        "customer_name": "👤 Customer Name",
        "total_amount": "💰 Total Amount",
        "welcome_bonus_amount": "🎁 Welcome Bonus",
    }
    
    # Display each extraction
    for field_key, display_name in field_display.items():
        if field_key not in visual_data:
            continue
        
        extraction = visual_data[field_key]
        self._create_visual_card(display_name, extraction)
    
    # Update canvas scroll region
    self.visual_frame.update_idletasks()

def _create_visual_card(self, title, extraction_data):
    """Create a card showing one visual extraction."""
    # Card container
    card = tk.Frame(self.visual_frame,
                   bg=CARD_BG_COLOR,
                   relief=tk.RAISED,
                   borderwidth=1)
    card.pack(fill=tk.X, padx=5, pady=5)
    
    # Header
    header = tk.Frame(card, bg="#2A2A2A")
    header.pack(fill=tk.X)
    
    tk.Label(header,
             text=title,
             font=("Segoe UI", 10, "bold"),
             fg=TEXT_COLOR,
             bg="#2A2A2A").pack(side=tk.LEFT, padx=10, pady=6)
    
    # Confidence badge
    confidence = extraction_data.get("confidence", 0)
    if confidence >= 80:
        badge_color = SUCCESS_COLOR
    elif confidence >= 60:
        badge_color = WARNING_COLOR
    else:
        badge_color = ERROR_COLOR
    
    tk.Label(header,
             text=f"{confidence}%",
             font=("Segoe UI", 9, "bold"),
             fg=badge_color,
             bg="#2A2A2A").pack(side=tk.RIGHT, padx=10, pady=6)
    
    # Body
    body = tk.Frame(card, bg=CARD_BG_COLOR)
    body.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
    
    # Load and display image
    image_b64 = extraction_data.get("image_base64")
    if image_b64:
        try:
            # Decode image
            image_bytes = base64.b64decode(image_b64)
            image = Image.open(io.BytesIO(image_bytes))
            
            # Resize to fit (max width 350px, max height 150px)
            max_width = 350
            max_height = 150
            image.thumbnail((max_width, max_height), Image.Resampling.LANCZOS)
            
            # Convert to PhotoImage
            photo = ImageTk.PhotoImage(image)
            self.extraction_images.append(photo)  # Keep reference
            
            # Display image
            img_label = tk.Label(body, image=photo, bg=CARD_BG_COLOR)
            img_label.pack(pady=(0, 8))
            
        except Exception as e:
            logging.error(f"Error displaying visual extraction image: {e}")
    
    # Display extracted value
    value = extraction_data.get("value", "N/A")
    if value and str(value).strip() and str(value).strip().lower() != 'null':
        value_frame = tk.Frame(body, bg="#1E1E1E", relief=tk.FLAT)
        value_frame.pack(fill=tk.X, pady=(0, 5))
        
        tk.Label(value_frame,
                 text=f"Value: {value}",
                 font=("Segoe UI", 9),
                 fg=TEXT_COLOR,
                 bg="#1E1E1E",
                 wraplength=330,
                 justify=tk.LEFT).pack(padx=8, pady=6, anchor="w")
```

#### 2.3 Integrate Visual Loading into Document Selection

Modify the `load_selected_pdf_document()` method:

```python
def load_selected_pdf_document(self, doc_dict):
    """Load PDF and display extracted data + visual confirmations."""
    # ... (existing PDF loading code) ...
    
    # Load visual confirmations (NEW!)
    extracted_data = doc_dict.get("extracted_data", {})
    visual_data = extracted_data.get("visual_extractions", {})
    self.load_visual_confirmations(visual_data)
    
    # ... (rest of existing code) ...
```

---

### Step 3: Update Data Flow to Preserve Visual Extractions

#### 3.1 Ensure Visual Data is Saved to History

**File**: `automate_login.py`  
**Function**: `save_row_to_history()`

Make sure the visual_extractions are included when saving:

```python
def save_row_to_history(row_data, customer_name, claim_date):
    # ... (existing code) ...
    
    # Ensure visual_extractions are preserved in document data
    for doc in row_data.get("documents", []):
        extracted = doc.get("extracted_data", {})
        # visual_extractions should already be in extracted_data from our modification
        # Just verify it's there
        if "visual_extractions" not in extracted:
            extracted["visual_extractions"] = {}
    
    # ... (rest of existing code) ...
```

---

## 🎨 UI Enhancements for Responsiveness

### Make UI Responsive

Add window resize handlers:

```python
def __init__(self):
    # ... (existing init code) ...
    
    # Bind resize event
    self.bind("<Configure>", self.on_window_resize)
    
def on_window_resize(self, event):
    """Handle window resize for responsive layout."""
    if event.widget == self:
        width = event.width
        height = event.height
        
        # Adjust panel weights based on window size
        if width < 1200:
            # Smaller window: hide visual panel or stack vertically
            # You can implement collapsible panels here
            pass
        else:
            # Normal 3-column layout
            pass
```

---

## 🧪 Testing the Visual Confirmation Feature

### Test Steps:

1. **Run the automation** on a sample invoice
2. **Check the extraction** includes `visual_extractions` in the JSON
3. **Open the UI** and select the processed claim
4. **Verify** that the right panel shows cropped images of:
   - Dealer stamp
   - Signatures
   - Invoice number
   - Other fields
5. **Confirm** that clicking on different documents updates the visual panel

### Example Visual Extraction Data Structure:

```json
{
  "document_type": "INVOICE",
  "invoice_number": "INV-2026-00123",
  "chassis_number": "MA1TA2E3BM5K67890",
  "visual_extractions": {
    "invoice_number": {
      "value": "INV-2026-00123",
      "confidence": 95,
      "bbox": [120, 85, 350, 115],
      "image_base64": "iVBORw0KGgoAAAANS..."
    },
    "chassis_number": {
      "value": "MA1TA2E3BM5K67890",
      "confidence": 92,
      "bbox": [120, 145, 450, 175],
      "image_base64": "iVBORw0KGgoAAAANS..."
    },
    "seal_stamp_dealer_name": {
      "value": "XYZ Motors Pvt Ltd",
      "confidence": 88,
      "bbox": [850, 650, 1050, 850],
      "image_base64": "iVBORw0KGgoAAAANS..."
    }
  }
}
```

---

## 🚀 Alternative: Use GPT-4 Vision with Grounding DINO

If GPT-4o-mini doesn't provide accurate bounding boxes, consider:

### Option A: Use Local Object Detection

```python
# Install: pip install groundingdino-py
from groundingdino import GroundingDINO

def detect_entities_with_grounding_dino(image_path, text_prompts):
    """
    Use Grounding DINO to detect entities in image.
    
    Args:
        image_path: Path to image
        text_prompts: List of text descriptions, e.g. ["dealer stamp", "signature"]
    
    Returns:
        dict of {prompt: [(bbox, confidence), ...]}
    """
    model = GroundingDINO()
    detections = model.detect(image_path, text_prompts)
    return detections
```

### Option B: Use EasyOCR + Fuzzy Matching

Since you already have EasyOCR working in `extract_disclaimer.py`, you can:

1. Run EasyOCR to get all text bounding boxes
2. Use fuzzy matching to find the boxes containing extracted values
3. Crop those regions

```python
def find_bbox_for_value(ocr_results, target_value):
    """Find bounding box for a specific value in OCR results."""
    from rapidfuzz import fuzz
    
    best_match = None
    best_score = 0
    
    for bbox, text, conf in ocr_results:
        score = fuzz.ratio(text.lower(), target_value.lower())
        if score > best_score and score > 70:
            best_score = score
            best_match = bbox
    
    return best_match
```

---

## 📊 Benefits of Visual Confirmation

✅ **Quality Assurance**: Instantly see what the AI detected  
✅ **Error Detection**: Spot incorrect extractions quickly  
✅ **Training**: Understand AI behavior patterns  
✅ **Confidence**: Visual proof for audits  
✅ **Debugging**: Identify poor image quality issues  

---

## 🎯 Next Steps

1. ✅ Implement bounding box extraction in OpenAI prompt
2. ✅ Add visual confirmation extraction function
3. ✅ Create visual panel in UI
4. ✅ Test with sample invoices
5. ✅ Fine-tune display and responsiveness

**Want me to create the complete working code files for you?** Let me know!
