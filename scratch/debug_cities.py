import urllib.request
import csv
import io
import re

sheet_url = "https://docs.google.com/spreadsheets/d/1TCWi0Xn9fkK2lAsNp0a08gh3TnCbXvFKqmB8eChJuHo/export?format=csv&gid=717771316"
print(f"Fetching from {sheet_url}...")

req = urllib.request.Request(
    sheet_url, 
    headers={'User-Agent': 'Mozilla/5.0'}
)
with urllib.request.urlopen(req, timeout=10) as response:
    content = response.read().decode('utf-8')
    
reader = csv.reader(io.StringIO(content))
rows = list(reader)

welcome_rows = []
current_section = None
for idx, row in enumerate(rows):
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
            # Header
            print("Welcome Headers:", row)
            continue
        welcome_rows.append(row)

print(f"Total welcome rows parsed: {len(welcome_rows)}")

cities = set()
for r in welcome_rows:
    region = r[7].strip().upper() if len(r) > 7 and r[7].strip() else "COMMON"
    cities.add(region)
    brand = r[0].strip().upper()
    mm_contrib_str = r[3].strip() if len(r) > 3 else "0"
    credit_note_str = r[6].strip() if len(r) > 6 else "0"
    if "VEERO" in brand:
        print(f"Brand: {brand} | City: {region} | MM Contrib: {mm_contrib_str} | Credit Note: {credit_note_str}")

print("\nDistinct Cities in Sheet:")
print(sorted(list(cities)))
