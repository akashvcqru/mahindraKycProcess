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
    digits = "".join(re.findall(r'\d+', cleaned))
    print(f"Digits snippet (first 100): {digits[:100]}")
    target_str = str(int(target_amount))
    print(f"Target string: {target_str}")
    if target_str in digits:
        return True
    return False

# Entire extracted text from task-305
text = """Mahindra VEER Mk TOWER PODIKKUNDU KANNUR KERALA 670004 STATEMENT OF ACCOUNT GST NO 32AFYPV741JB2Z7 VEER 15.58 48 PODIRKUNDU 13/06/2026 From 01/04/2026 To 13/06/2026 LANCY BABU F SANDRA VILLA MARIYAN KADACHIRA Currency: RS Aecount Number 12058284 TYPE NO DATE DESCRIPTION DFPT INVOICE DE CRE BALANCE Opcning Balance @@O RV 0774 18052026 BOOKING CASH RECEIVED HOz L,om0 0 ~L,onu U0 FROM LANCYDARU FOR PICKUF 2246 2105/2026 DO AMOUNT RECEIVED HO? 2246 4u2 50| U0 29,0},S01 00 FROM CHOLAMANDALAM FINANCE ON BFHALF OF LANCY BABU / 31052026 VEERO !SXXL SD V6 VS 20 902 S0U m0 ~Lmi 00 JV ZJz| 09 0o20zo MAGMA HDI GENERAL H02 P0ztoudi 27,884 Q0 16,833,00 WNSURANCE CO LID JV 333 09/062026 ROAD TAX FAYAHLE HOI T6F16867 17,60U QU 4abo JV 2J19 10/062ozo FASTAG - PARK HOI TGEI686 7 64n 00 45,03] 00 CN 14 10,062026 WELCOM HONUS GIVEN T0 VS VOvz7aoO 15 (X) Ou J0.0J3 00 LANCY BABU P(VS27AQ00A2I ~INV27A(HI26)*[6E46867 CN 19 10,0672026 OEM DISCOUNT GIVENTO VS VOVZTAQU S0.,00 m0 19,907 Wu LANCY BABU F(VS27A000I2I ~INV27AO0I26)*16E16x67 P 1968 1J06/2026 BALANCE AMOUNT REFUND O? 1968 19.967,0 0 00 TO LANCY BABU 0.uu "Totl 9,68,501,000 9,68,S0i Ouo Page WKundU KANNU VFER P00019"""

print("Checking match on entire text...")
res = check_amount_match(text, 15000)
print(f"Match result: {res}")
