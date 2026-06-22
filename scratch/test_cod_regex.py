import re
from rapidfuzz import fuzz

text = """DigiELV TRANSFER CERTIFICATE OF DEPOSIT Certilicate_No CQD2O26046DL13CQ0333 The certificate has been traded and transferred to HARISH M B wilh Mobile No **t*5373, PAN No **+* 797G from SHAKEEL AHMAD, perlinent to the Vehicie Registration No DL13CQ0333 The Cerlificate of Deposit (CD) was issued on 17-04-2026 and is valid until 16-04-2029. Vehicle Details: Make HYUNDAI MOTOR INDIA LTD Model SANTRO GL Vehicle Category/Class LMV Vehicle Type Non Transport Fuel Type PETROL Cubic Capacity 1086.0 Seating Capacily(in all) : 5 Year of Manufacturing 06-2011 Unladen Weight(kgs) 854 Numiber of Cylinders 4 Regisleied Gross Vehicle Weight(*gs) 0 Wheelb-se(nim) 0 The owner of this certificate is entitled to claim the following benefits on purchase of one new vehicle These benefits can be availed only once_ 1. Regislration fee Waiver as per Rule 81 of CMVR, 1989_ 2. Corcession 0n motor vehicle tax as prescribed in the state of purchase of new vehicle 3. Auto OEM discount as per the discretion of auto OEM deaiers Trade Date: 30-05-2026 Trade No: 33300526335345421553 Disclaimer: This_certificate needs_tobe_validatedat the_time_of utilizetion Trading Infomation You can also trade this certificate by following these 4 basic steps Clici a TrzdvorGo C@urPietc Es;eC_i? Ourer Alocates ard t Trf-P-rd Se" Fuchaze Fiice Buyer Confim:s Digilally sigued by Tmlir Dxie: 202605 3014*62.13 IST R---m: AUTHENTICATION Lru Atinn: Irfia J"""

# 1. Test Certificate No extraction
cert_no = None
cert_no_match = re.search(r'(?:Cert[A-Za-z0-9_]*|Deposit)[:\s_-]+(C[OQ0][D0][A-Z0-9OoQ_]+)\b', text, re.IGNORECASE)
if cert_no_match:
    cert_no = cert_no_match.group(1)
else:
    cert_no_match = re.search(r'\b(C[OQ0][D0][A-Z0-9OoQ]+)\b', text, re.IGNORECASE)
    if cert_no_match:
        cert_no = cert_no_match.group(1)

if cert_no:
    cert_no_upper = cert_no.upper()
    if len(cert_no_upper) > 3:
        prefix = cert_no_upper[:3]
        if prefix[0] == 'C' and prefix[1] in 'OQ0' and prefix[2] in 'D0':
            cert_no = "COD" + cert_no[3:]

print(f"Extracted Certificate No: {cert_no}")

# 2. Test Registration No extraction
reg_no = None
reg_no_match = re.search(r'Reg[A-Za-z\s]*No\s*[:\.-]?\s*([A-Z0-9]+)', text, re.IGNORECASE)
if reg_no_match:
    reg_no = reg_no_match.group(1).upper()

print(f"Extracted Registration No: {reg_no}")

# 3. Test Transferred to Name extraction
transferred_name = None
transferred_match = re.search(r'transferred\s+to\s+([A-Za-z\s\.\-]+?)\s+(?:with|wilh|Mobile|PAN)\b', text, re.IGNORECASE)
if transferred_match:
    transferred_name = transferred_match.group(1).strip()

print(f"Extracted Transferred to Name: {transferred_name}")

# Let's perform validation logic tests
old_vehicle_details = {
    "Chassis No": "COD2026046DL13CQ0333",
    "Reg. No": "DL13CQ0333",
    "Customer Name": "HARISH M B"
}

def normalize_str(s):
    if not s:
        return ""
    return re.sub(r'[^A-Z0-9]', '', s.upper())

def replace_confusions(s):
    return s.replace('L', '1').replace('I', '1').replace('O', '0').replace('Q', '0')

def compare_values_robust(doc_val, web_val, fuzzy_threshold=80):
    if not doc_val or not web_val:
        return "UNKNOWN", 0.0
    
    norm_doc = normalize_str(doc_val)
    norm_web = normalize_str(web_val)
    if norm_doc == norm_web:
        return "MATCH", 100.0
        
    if replace_confusions(norm_doc) == replace_confusions(norm_web):
        return "MATCH (OCR adjusted)", 100.0
        
    if norm_doc in norm_web or norm_web in norm_doc:
        return "MATCH (Substring)", 100.0
        
    score = fuzz.token_sort_ratio(doc_val.lower(), web_val.lower())
    if score >= fuzzy_threshold:
        return f"MATCH (Fuzzy: {score:.1f}%)", score
        
    return f"MISMATCH ({score:.1f}%)", score

# Validate Certificate
status_cert, score_cert = compare_values_robust(cert_no, old_vehicle_details["Chassis No"])
print(f"Cert status: {status_cert}, score: {score_cert}")

# Validate Reg No
status_reg, score_reg = compare_values_robust(reg_no, old_vehicle_details["Reg. No"])
print(f"Reg status: {status_reg}, score: {score_reg}")

# Validate Name
status_name, score_name = compare_values_robust(transferred_name, old_vehicle_details["Customer Name"])
print(f"Name status: {status_name}, score: {score_name}")
