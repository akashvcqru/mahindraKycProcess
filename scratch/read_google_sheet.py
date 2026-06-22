import urllib.request
import csv
import io

url = "https://docs.google.com/spreadsheets/d/1TCWi0Xn9fkK2lAsNp0a08gh3TnCbXvFKqmB8eChJuHo/export?format=csv&gid=717771316"

try:
    print(f"Fetching URL: {url}")
    req = urllib.request.Request(
        url, 
        headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
    )
    with urllib.request.urlopen(req) as response:
        content = response.read().decode('utf-8')
        print("Successfully fetched sheet data!")
        
        # Parse CSV
        reader = csv.reader(io.StringIO(content))
        rows = list(reader)
        print(f"Total rows read: {len(rows)}")
        print("\nFirst 30 rows:")
        for idx, row in enumerate(rows[:30]):
            print(f"Row {idx:02d}: {row}")
            
except Exception as e:
    print(f"Error fetching Google Sheet: {e}")
