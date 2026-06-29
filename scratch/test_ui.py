import json

with open('ui_history.json', 'r', encoding='utf-8') as f:
    history = json.load(f)

for claim in history[-3:]:
    print(f"Row {claim.get('row_idx')}")
    for doc_dict in claim.get('documents', []):
        extracted_data = doc_dict.get('extracted_data', {})
        visual_data = extracted_data.get('visual_extractions', {})
        print(f"  Doc {doc_dict.get('file_name')}: visual_data len={len(visual_data)}, keys={list(visual_data.keys())}")
