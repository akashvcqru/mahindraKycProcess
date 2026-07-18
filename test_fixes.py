import sys, os
os.environ['AI_PROVIDER'] = 'PYTHON'
sys.path.insert(0, '.')

# Test 1: MFC file now classified as DISCLAIMER
from welcome_scheme.processor import classify_document
result = classify_document(r'c:\Users\admin\Desktop\robbinmahindra\documents\DIPTI DEURI\MFC-1782296882290.pdf')
print(f'MFC file classified as: {result}  (expected: DISCLAIMER)')

result2 = classify_document(r'c:\Users\admin\Desktop\robbinmahindra\documents\DIPTI DEURI\INVOICE-1782296882459.pdf')
print(f'INVOICE file classified as: {result2}  (expected: INVOICE)')

# Test 2: Date parsing for OCR-noisy strings
from datetime import datetime
import re

def parse_d_test(s):
    if not s or not s.strip():
        return None
    s_clean = s.strip()
    s_clean = re.sub(r'\b(st|nd|rd|th)\b', '', s_clean, flags=re.IGNORECASE)
    s_clean = re.sub(r'\bof\b', '', s_clean, flags=re.IGNORECASE)
    s_clean = re.sub(r'\s+', ' ', s_clean)
    s_clean = re.sub(r'[^0-9]', '-', s_clean)
    s_clean = re.sub(r'-+', '-', s_clean).strip('-')
    digits = re.sub(r'[^0-9]', '', s_clean)
    if len(digits) == 8:
        day, month, year = digits[:2], digits[2:4], digits[4:]
        s_clean = f'{day}-{month}-{year}'
    elif len(digits) == 6:
        day, month, year = digits[:2], digits[2:4], '20' + digits[4:]
        s_clean = f'{day}-{month}-{year}'
    else:
        parts = [p for p in s_clean.split('-') if p.strip() and p.strip().isdigit()]
        if len(parts) >= 3:
            year_parts = [p for p in parts if len(p) == 4]
            day_parts = [p for p in parts if 1 <= len(p) <= 2 and p != (year_parts[0] if year_parts else '')]
            if year_parts and len(day_parts) >= 2:
                s_clean = f'{day_parts[0]}-{day_parts[1]}-{year_parts[0]}'
    for fmt in ('%d-%m-%Y','%d/%m/%Y','%Y-%m-%d','%d-%b-%Y','%d.%m.%Y','%d-%m-%y','%d/%m/%y','%y-%m-%d','%d-%b-%y','%d.%m.%y'):
        try:
            return datetime.strptime(s_clean, fmt).date()
        except:
            pass
    return None

print()
print('=== DATE PARSING TESTS (OCR noise) ===')
ocr_dates = ["12,0 S' 2026", '12.252026', '12/05/2026', '12 May 2026', '12-MAY-26', '12.0']
for test in ocr_dates:
    result = parse_d_test(test)
    print(f"  {repr(test):30s} -> {result}")

print()
print('=== CHASSIS MATCHING TESTS ===')
from welcome_scheme.disclaimer_validation import compare_values_robust as dis_cmp
from welcome_scheme.invoice_validation import compare_values_robust as inv_cmp
tests = [
    ('MAQV22VXTLE45840', 'T6E15840', 'Disclaimer chassis'),
    ('MAJVEVXTLE45840', 'T6E15840', 'Disclaimer chassis (OCR variant)'),
    ('MATUVZCVXTGE15840ENGINE', 'T6E15840', 'Invoice chassis'),
]
for doc_ch, portal_ch, label in tests:
    r = dis_cmp(doc_ch, portal_ch)
    print(f'  {label}: {doc_ch} vs {portal_ch} -> {r}')
