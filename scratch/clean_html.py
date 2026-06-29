import re

with open(r'c:\Users\admin\Desktop\robbinmahindra\invoice_analyzer.html', 'r', encoding='utf-8') as f:
    content = f.read()

# The CROPS array contains base64 images which make the file very large
content = re.sub(r'const CROPS = \[.*?\];', 'const CROPS = []; // Truncated by script', content, flags=re.DOTALL)

with open(r'c:\Users\admin\Desktop\robbinmahindra\scratch\invoice_analyzer_clean.html', 'w', encoding='utf-8') as f:
    f.write(content)
