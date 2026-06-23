import urllib.request
import csv
import io

sheet_url = "https://docs.google.com/spreadsheets/d/1TCWi0Xn9fkK2lAsNp0a08gh3TnCbXvFKqmB8eChJuHo/export?format=csv&gid=717771316"
req = urllib.request.Request(sheet_url, headers={'User-Agent': 'Mozilla/5.0'})
with urllib.request.urlopen(req) as response:
    content = response.read().decode('utf-8')

reader = csv.reader(io.StringIO(content))
rows = list(reader)

print("Total rows:", len(rows))
current_section = None
for i, row in enumerate(rows):
    if not row or not any(cell.strip() for cell in row):
        continue
    first_cell = row[0].strip().lower()
    if "welcome bonus" in first_cell:
        current_section = "welcome"
        print(f"\n--- Row {i}: Section Welcome Bonus ---")
        print("Header:", row)
        continue
    elif "scrappage scheme" in first_cell:
        current_section = "scrappage"
        print(f"\n--- Row {i}: Section Scrappage Scheme ---")
        print("Header:", row)
        continue
    
    if current_section == "welcome" and "brand" in row[0].lower():
        print(f"Sub-header Welcome (Row {i}):", row)
    elif current_section == "scrappage" and "brand" in row[0].lower():
        print(f"Sub-header Scrappage (Row {i}):", row)
    elif i < 30:
        print(f"Row {i} ({current_section}):", row[:10])
