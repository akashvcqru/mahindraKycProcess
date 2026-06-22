import urllib.request
import csv
import io
import re

_cached_schemes = None
_cached_contributions = None

def fetch_google_sheet_data():
    global _cached_schemes, _cached_contributions
    if _cached_schemes is not None and _cached_contributions is not None:
        return _cached_schemes, _cached_contributions

    sheet_url = "https://docs.google.com/spreadsheets/d/1TCWi0Xn9fkK2lAsNp0a08gh3TnCbXvFKqmB8eChJuHo/export?format=csv&gid=717771316"
    
    print(f"Fetching Google Sheet CSV from: {sheet_url}")
    req = urllib.request.Request(
        sheet_url, 
        headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
    )
    with urllib.request.urlopen(req, timeout=10) as response:
        content = response.read().decode('utf-8')
        
    reader = csv.reader(io.StringIO(content))
    rows = list(reader)
    
    if not rows:
        raise Exception("Google Sheet returned empty data.")

    schemes = {
        "welcome": {},
        "scrappage": {}
    }
    contributions = {
        "welcome": {},
        "scrappage": {}
    }
    
    current_section = None
    
    for idx, row in enumerate(rows):
        if not row:
            continue
        first_cell = row[0].strip().lower() if row else ""
        if "welcome bonus" in first_cell and not any(cell.strip() for cell in row[1:]):
            current_section = "welcome"
            print(f"Row {idx:02d}: Switched current_section to 'welcome'")
            continue
        elif "scrappage scheme" in first_cell and not any(cell.strip() for cell in row[1:]):
            current_section = "scrappage"
            print(f"Row {idx:02d}: Switched current_section to 'scrappage'")
            continue
            
        if not any(cell.strip() for cell in row):
            if current_section:
                print(f"Row {idx:02d}: Empty row, resetting current_section from {current_section}")
            current_section = None
            continue
            
        if current_section == "welcome":
            if "brand" in row[0].lower():
                continue
            region = row[7].strip() if len(row) > 7 else ""
            print(f"Row {idx:02d}: Processing welcome row. Brand={row[0]}, Region={region}")
            if region and region.lower() not in ["common", "bangalore"]:
                print(f"Row {idx:02d}: Skipping because region {region} is not common/bangalore")
                continue
                
            brand = row[0].strip().upper()
            if not brand:
                continue
                
            mm_contrib_str = row[3].strip() if len(row) > 3 else "0"
            credit_note_str = row[6].strip() if len(row) > 6 else "0"
            
            try:
                mm_contrib = float(''.join(c for c in mm_contrib_str if c.isdigit() or c == '.'))
                credit_note = float(''.join(c for c in credit_note_str if c.isdigit() or c == '.'))
                
                contributions["welcome"][brand] = mm_contrib
                schemes["welcome"][brand] = credit_note
                print(f"Row {idx:02d}: Added welcome bonus for {brand}: {mm_contrib} / {credit_note}")
            except Exception as e:
                print(f"Row {idx:02d}: Skipping welcome row {row} due to parsing error: {e}")
            
        elif current_section == "scrappage":
            if "brand" in row[0].lower():
                continue
                
            brand_field = row[0].strip()
            if not brand_field:
                continue
                
            mm_contrib_str = row[1].strip() if len(row) > 1 else "0"
            credit_note_str = row[4].strip() if len(row) > 4 else "0"
            
            try:
                mm_contrib = float(''.join(c for c in mm_contrib_str if c.isdigit() or c == '.'))
                credit_note = float(''.join(c for c in credit_note_str if c.isdigit() or c == '.'))
                
                sub_brands = [b.strip().upper() for b in re.split(r'[|/]', brand_field) if b.strip()]
                for b in sub_brands:
                    contributions["scrappage"][b] = mm_contrib
                    schemes["scrappage"][b] = credit_note
                print(f"Row {idx:02d}: Added scrappage for {sub_brands}: {mm_contrib} / {credit_note}")
            except Exception as e:
                print(f"Row {idx:02d}: Skipping scrappage row {row} due to parsing error: {e}")
                
    _cached_schemes = schemes
    _cached_contributions = contributions
    return _cached_schemes, _cached_contributions

# Load and print
s, c = fetch_google_sheet_data()
print("\n--- SCHEMES (Credit Note without GST) ---")
import pprint
pprint.pprint(s)
print("\n--- CONTRIBUTIONS ---")
pprint.pprint(c)
