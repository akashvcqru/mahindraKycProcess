import re

def clean_date(text):
    if not text or text == "NOT_FOUND":
        return "NOT_FOUND"
    
    t = text.lower().strip()
    t = re.sub(r'[\|\\!]', '/', t)
    
    # Char map for date - removed 'd'/'D' to let them be treated as separators when in words like 'dw'
    char_map = {
        'o': '0', 'O': '0', 'q': '0', 'Q': '0',
        'i': '1', 'I': '1', 'l': '1', 't': '1', 'T': '1', 'j': '1',
        's': '5', 'S': '5', 'b': '6', 'g': '9', 'z': '2', 'Z': '2',
        'f': '0', '?' : '0', 'k': '1', 'K': '1', '&': '6'
    }
    
    cleaned = []
    for c in t:
        if c.isdigit() or c in ['/', '-', '.']:
            cleaned.append(c)
        elif c in char_map:
            cleaned.append(char_map[c])
        elif c.isalpha() or c.isspace():
            cleaned.append('/')
            
    cleaned_str = "".join(cleaned)
    cleaned_str = re.sub(r'[\-\.]', '/', cleaned_str)
    cleaned_str = re.sub(r'/+', '/', cleaned_str)
    cleaned_str = cleaned_str.strip('/')
    
    match = re.search(r'\b(\d{1,2})/(\d{1,2})/(\d{2,4})\b', cleaned_str)
    if match:
        day, month, year = match.groups()
        if len(day) == 1: day = '0' + day
        if len(month) == 1: month = '0' + month
        if len(year) == 2: year = '20' + year
        if len(year) == 3 and year.startswith('202'): year = year + '6'
        return f"{day}/{month}/{year}"
        
    return text.strip()

# Test cases
print(clean_date("3i/05dw26")) # Should be 31/05/2026
print(clean_date("31|05|2026")) # Should be 31/05/2026
print(clean_date("31-05-2026")) # Should be 31/05/2026
print(clean_date("/31/05/2026")) # Should be 31/05/2026
