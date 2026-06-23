import re
from rapidfuzz import fuzz

def normalize_ocr_amount_text(text):
    # Convert to lowercase
    cleaned = text.lower()
    
    # Standard replacement of parenthesis or common OCR brackets representing zeros
    cleaned = cleaned.replace('(x)', '000').replace('(o)', '000').replace('()', '000')
    cleaned = cleaned.replace('[x]', '000').replace('[o]', '000').replace('[]', '000')
    
    # Map common OCR letters that represent digits
    # 'w' -> '00' (very common when '00' is read as 'w')
    cleaned = cleaned.replace('w', '00')
    
    # 'ou' -> '.00', 'o0' -> '.00', 'oo' -> '.00'
    cleaned = cleaned.replace('ou', '00')
    cleaned = cleaned.replace('o0', '00')
    cleaned = cleaned.replace('oo', '00')
    
    # Let's clean up characters:
    # 'i', 'l', '|', '[', ']' -> '1'
    # 'o', 'u', 'q' -> '0'
    # 's' -> '5'
    # 'b' -> '8'
    # 'z' -> '2'
    # 'g' -> '6'
    
    # We will do these replacements character by character but only if they are close to other digits
    # or inside tokens that look like numbers. Let's do a general mapping for digit extraction.
    mapped_chars = []
    char_map = {
        'i': '1', 'l': '1', '|': '1', '[': '1', ']': '1',
        'o': '0', 'u': '0', 'q': '0',
        's': '5',
        'b': '8',
        'z': '2',
        'g': '6'
    }
    
    for char in cleaned:
        if char in char_map:
            mapped_chars.append(char_map[char])
        else:
            mapped_chars.append(char)
            
    mapped_text = "".join(mapped_chars)
    return mapped_text

def check_amount_match(line_text, target_amount):
    target_str = str(int(target_amount))
    
    # Try digits match with mapped text
    mapped = normalize_ocr_amount_text(line_text)
    digits = "".join(re.findall(r'\d+', mapped))
    print(f"Mapped: {mapped}")
    print(f"Digits: {digits}")
    
    if target_str in digits:
        return True
        
    return False

# Test cases
lines = [
    # 150 DPI OCR line
    "CN 14 10,062026 WELCOM HONUS GIVEN T0 VS VOvz7aoO 15 (X) Ou J0.0J3 00 LANCY BABU P(VS27AQ00A2I ~INV27A(HI26)*[6E46867",
    # 300 DPI OCR line
    "10062026 WELCOM HJONUS GIVEN T0 VS VOv27aQO; I5 W0 J.OJ} 0 LANCY BAHU P(VS27A000/2I ~INV27A(MII26/*[6E16867"
]

for idx, line in enumerate(lines):
    print(f"\n--- Test {idx+1} ---")
    res = check_amount_match(line, 15000)
    print(f"Result for 15000: {res}")
