import json

with open('ui_history.json', 'r', encoding='utf-8') as f:
    history = json.load(f)

for claim in history[-1:]:
    print(f"Row {claim.get('row_idx')}")
    for doc in claim.get('documents', []):
        print(f"Doc: {doc.get('filename')}")
        extracted = doc.get('extracted_data', {})
        print("Extracted Invoice No:", extracted.get('invoice_number'))
        print("Bboxes:", extracted.get('bounding_boxes', {}))
