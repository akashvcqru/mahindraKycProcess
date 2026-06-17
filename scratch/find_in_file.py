import sys

def search_file(filepath, query):
    encodings = ['utf-8', 'utf-16', 'utf-16-le', 'utf-16-be', 'latin-1']
    content = None
    for enc in encodings:
        try:
            with open(filepath, 'r', encoding=enc) as f:
                content = f.read()
                print(f"Successfully read file with encoding: {enc}")
                break
        except Exception as e:
            continue
            
    if content is None:
        print("Failed to read file with any encoding.")
        return
        
    lines = content.splitlines()
    print(f"Total lines: {len(lines)}")
    matches = 0
    for idx, line in enumerate(lines):
        if query.lower() in line.lower():
            print(f"Line {idx+1}: {line.strip()[:120]}")
            matches += 1
            if matches >= 100:
                print("Too many matches, truncating...")
                break
    if matches == 0:
        print(f"No matches found for query: '{query}'")

if __name__ == '__main__':
    query = sys.argv[1] if len(sys.argv) > 1 else 'def'
    search_file(r'c:\Users\admin\Desktop\robbinmahindra\automate_login.py', query)
