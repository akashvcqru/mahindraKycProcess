import re

def find_floats_in_line(line_text):
    cleaned = line_text.lower()
    cleaned = cleaned.replace('(x)', '000').replace('(o)', '000').replace('()', '000')
    cleaned = cleaned.replace('ou', '.00').replace('o0', '.00').replace('oo', '.00')
    cleaned = re.sub(r'[^0-9\.\-]', ' ', cleaned)
    tokens = cleaned.split()
    floats = []
    for t in tokens:
        t = t.strip('.-')
        if not t:
            continue
        if t.count('.') > 1:
            parts = t.split('.')
            t = "".join(parts[:-1]) + "." + parts[-1]
        try:
            floats.append(float(t))
        except ValueError:
            pass
    return floats

def check_amount_match(line_text, target_amount):
    floats = find_floats_in_line(line_text)
    print(f"Floats: {floats}")
    for val in floats:
        if abs(val - target_amount) < 1.0:
            return True
            
    cleaned = line_text.lower()
    cleaned = cleaned.replace('(x)', '000').replace('(o)', '000').replace('()', '000')
    cleaned = cleaned.replace('ou', '00').replace('o0', '00').replace('oo', '00')
    print(f"Cleaned for digits: {cleaned}")
    digits = "".join(re.findall(r'\d+', cleaned))
    print(f"Digits: {digits}")
    target_str = str(int(target_amount))
    print(f"Target: {target_str}")
    if target_str in digits:
        return True
    return False

line_text = "CN 14 10,062026 WELCOM HONUS GIVEN T0 VS VOvz7aoO 15 (X) Ou J0.0J3 00 LANCY BABU P(VS27AQ00A2I ~INV27A(HI26)*[6E46867"
print(check_amount_match(line_text, 15000))
