with open('automate_login.py', 'r', encoding='utf-8') as f:
    content = f.read()

target = '''        # Explicit normalizations
        if doc_type in ["AADHAAR", "ADHR"]:
            doc_type = "ADHAR"
        elif doc_type in ["DISCLAIMER", "DSC"]:
            doc_type = "DISCLAIMER"'''

replacement = '''        # Explicit normalizations
        if doc_type in ["AADHAAR", "ADHR"]:
            doc_type = "ADHAR"
        elif doc_type in ["DISCLAIMER", "DSC"]:
            doc_type = "DISCLAIMER"
        elif doc_type in ["INVOICE", "TAX INVOICE", "GST INVOICE", "TAX_INVOICE"]:
            doc_type = "INVOICE"'''

if target in content:
    content = content.replace(target, replacement)
    with open('automate_login.py', 'w', encoding='utf-8') as f:
        f.write(content)
    print("Successfully normalized TAX INVOICE to INVOICE")
else:
    print("Target block not found in automate_login.py")
