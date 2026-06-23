import urllib.request
import csv
import io
import re

def fetch_google_sheet_data():
    sheet_url = "https://docs.google.com/spreadsheets/d/1TCWi0Xn9fkK2lAsNp0a08gh3TnCbXvFKqmB8eChJuHo/export?format=csv&gid=717771316"
    
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
    
    for row in rows:
        if not row:
            continue
        first_cell = row[0].strip().lower() if row else ""
        if "welcome bonus" in first_cell and not any(cell.strip() for cell in row[1:]):
            current_section = "welcome"
            continue
        elif "scrappage scheme" in first_cell and not any(cell.strip() for cell in row[1:]):
            current_section = "scrappage"
            continue
            
        if not any(cell.strip() for cell in row):
            current_section = None
            continue
            
        if current_section == "welcome":
            if "brand" in row[0].lower():
                continue
            region = row[7].strip().upper() if len(row) > 7 and row[7].strip() else "COMMON"
            brand = row[0].strip().upper()
            if not brand:
                continue
                
            mm_contrib_str = row[3].strip() if len(row) > 3 else "0"
            credit_note_str = row[6].strip() if len(row) > 6 else "0"
            
            try:
                mm_contrib = float(''.join(c for c in mm_contrib_str if c.isdigit() or c == '.'))
                credit_note = float(''.join(c for c in credit_note_str if c.isdigit() or c == '.'))
                
                if brand not in contributions["welcome"]:
                    contributions["welcome"][brand] = []
                if brand not in schemes["welcome"]:
                    schemes["welcome"][brand] = []
                    
                contributions["welcome"][brand].append({"city": region, "amount": mm_contrib})
                schemes["welcome"][brand].append({"city": region, "amount": credit_note})
            except Exception as e:
                print(f"Skipping welcome row due to parsing error: {e}")
            
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
            except Exception as e:
                print(f"Skipping scrappage row due to parsing error: {e}")
                
    return schemes, contributions

def lookup_welcome_amount(brand_name, target_city, data_dict):
    brand_name = brand_name.strip().upper()
    target_city = target_city.strip().upper() if target_city else "COMMON"
    
    entries = None
    # 1. Exact match
    if brand_name in data_dict:
        entries = data_dict[brand_name]
    else:
        # 2. Substring match
        for key, val in data_dict.items():
            if key in brand_name or brand_name in key:
                entries = val
                break
                
    if not entries:
        # 3. Word-based match
        brand_words = [w for w in re.sub(r'[^A-Z0-9]', ' ', brand_name).split() if len(w) > 0]
        if brand_words:
            first_word = brand_words[0]
            if first_word == "NEW" and len(brand_words) > 1:
                first_word = brand_words[1]
            for key, val in data_dict.items():
                key_clean = re.sub(r'[^A-Z0-9]', ' ', key)
                if first_word in key_clean.split():
                    entries = val
                    break
                    
    if not entries:
        return None
        
    # Search for specific city match first
    for entry in entries:
        if entry["city"] == target_city:
            return entry["amount"]
            
    # Search for COMMON fallback
    for entry in entries:
        if entry["city"] == "COMMON":
            return entry["amount"]
            
    return None

# Load data
schemes, contributions = fetch_google_sheet_data()

# Test scenarios
test_cases = [
    ("VEERO", "KOLKATA"),
    ("VEERO", "BANGALORE"),
    ("VEERO", "COMMON"),
    ("VEERO", None),
    ("PICKUP", "KOLKATA"),
    ("PICKUP", "BANGALORE"),
]

print("=== DRY RUN TESTS FOR WELCOME BONUS ===")
for brand, city in test_cases:
    expected_contrib = lookup_welcome_amount(brand, city, contributions["welcome"])
    expected_scheme = lookup_welcome_amount(brand, city, schemes["welcome"])
    print(f"Brand: {brand:<8} | City: {str(city):<10} => M&M Contribution: {expected_contrib:<6} | Credit Note: {expected_scheme}")
