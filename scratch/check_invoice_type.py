with open('automate_login.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

for i, line in enumerate(lines):
    # Check for == "INVOICE" or in ["INVOICE"] or similar string comparisons
    if '"INVOICE"' in line or "'INVOICE'" in line:
        print(f"Line {i+1}: {line.strip()}")
