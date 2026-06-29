import re

with open(r'c:\Users\admin\Desktop\robbinmahindra\invoice_analyzer.html', 'r', encoding='utf-8') as f:
    content = f.read()

content = re.sub(r'const CROPS = \[.*?\];', 'const CROPS = []; // Truncated', content, flags=re.DOTALL)
content = re.sub(r'const PDF_B64 = \".*?\";', 'const PDF_B64 = \"\"; // Truncated', content, flags=re.DOTALL)

with open(r'c:\Users\admin\Desktop\robbinmahindra\scratch\invoice_analyzer_clean2.html', 'w', encoding='utf-8') as f:
    f.write(content)
