import re
from rapidfuzz import fuzz, process

# Sample texts from our OCR/Digital runs
lancy_disclaimer = """mahindra VeER MAHINDRA UliT Oaccee Customer Disclaimer for WELCOMEIScrappage Bonus through COD 1, LANCY BABU P , residing at SANDRA VILLA,MARIYAN COLONY KADACHIRA KADACHIRA $ 0, KANNUR,KERALA ,670621, do hereby solemnly affirm and declare as under: state and declare that am the actual and rightful owner/operator of the said Vehicle and have been incontinuous possession, custody, and use of it"""
lancy_pan = """3ir4azr) frtrot HRT RER INCOME TAX DEPARTMENT GOVT OF INDIA rrr cu7G *7d Permanent Account Number Card DQZPP2239C 1354i0  { 70A/ Name LANCY BABU P far #T 7TF / Father's Name LUIS 744iand Date o/ Birth 02/09/1970 TleR / Signature"""

raghul_disclaimer = """u NANT CARS l(glart FiiUTCnoice AA^t:\AMILE AT EVERY MILE hul Selvam , resi red at MYSORE on this 30 of MAy, 2026. ature of Customer: of Customer: S.Raghul Selvam Number: 8660778016 RITANANDAMAYI GO 1 ' I state and declare that I am the actual and rightful owner/operator of the said Vehicle and have been incontinuous possession, custody, and use of it i,tne Vehicl;,rl- o Registration Number: UK0416469 o Vehicle Make: Maruti o Vehicle Model (Not required for Scrappage Case) : Omni oR I am in lawful possession of certificate of Deposit (coD), with number - coD20260440uK0416469 againstRegistration number: uK0416469 (Appricabre onry for ,.rupprg. cases), 2' That the above-mentioned vehicle owned by me/coD has been brought by me to avail Loyalty/scrappagebenefit offered on New M&M vehicre undei the Loyarty/scirppugu program. o New Vehicle Moder: THAR Roxx srAR EDN p AT RWD EWT/BR o Chassis Number: T2E33121 o Engine Number:JWT4E5B975 3. That I undertake and confirm that: o All liabilities in"""
raghul_invoice = """TAX INVOICE +I ANANTCARS AUTO PBIV (Mahindra Authorised Dealer) ATE LIiJIITED .nlTl}# SPORT m tIT I LITY VEHICLES Sales lnvoi@ Karnataka BANK OF BARODA R270177555 S,RAGHUL SELVAM Customer Code: Name: Cust GSTIN: PAN No.l Aadhar No'l Phone Nol Add ress: R270'1 77555 S,RAGHUL SELVAI\,4 FMMP5671 5P xxxxxxxx0048 866077801 6 ]/O G SILAMBU SELVAN, NO"""

def clean_extracted_name(name_str):
    if not name_str:
        return ""
    name_str = re.sub(r'[^A-Za-z\s\.\-]', '', name_str) # keep letters, spaces, dots, hyphens
    name_str = re.sub(r'\s+', ' ', name_str)
    return name_str.strip()

def parse_cod_data(text, claim_customer_name):
    # 1. Certificate No
    cod_match = re.search(r'\b(COD[A-Z0-9]+)\b', text, re.IGNORECASE)
    cert_no = cod_match.group(0) if cod_match else None
    if not cert_no:
        # try searching for deposit numbers or similar
        fallback_match = re.search(r'certificate\s*of\s*Deposit\s*\(?coD\)?,\s*with\s*number\s*-\s*([A-Z0-9]+)', text, re.IGNORECASE)
        if fallback_match:
            cert_no = fallback_match.group(1)
            
    # 2. Extract Name Candidates
    name_candidates = []
    # Match I, [NAME], residing
    residing_matches = re.finditer(r'\b[I1]\s*,\s*([A-Za-z\s\.\-]+),\s*residing', text, re.IGNORECASE)
    for m in residing_matches:
        name_candidates.append(clean_extracted_name(m.group(1)))
        
    # Match Name of Customer / Customer Name
    customer_matches = re.finditer(r'(?:Customer|Name of Customer|Owner Name|Name)\s*[:\.-]?\s*([A-Za-z\s\.\-]+)', text, re.IGNORECASE)
    for m in customer_matches:
        name_candidates.append(clean_extracted_name(m.group(1)))
        
    # General fallback: check each word sequence / line
    # Split text by common separators and test fuzzy match
    best_candidate = None
    best_score = 0.0
    
    # We also do a fuzzy match of each candidate against claim_customer_name
    for cand in name_candidates:
        if len(cand) < 4:
            continue
        score = fuzz.token_sort_ratio(cand.lower(), claim_customer_name.lower())
        if score > best_score:
            best_score = score
            best_candidate = cand
            
    # If no candidate found via regex, do a sliding window or line-by-line check in the text
    if best_score < 70:
        lines = [line.strip() for line in re.split(r'[\n,\.]', text) if len(line.strip()) > 3]
        for line in lines:
            cleaned = clean_extracted_name(line)
            if len(cleaned) < len(claim_customer_name) - 5 or len(cleaned) > len(claim_customer_name) + 15:
                # Try partial match or sliding window
                pass
            score = fuzz.token_sort_ratio(cleaned.lower(), claim_customer_name.lower())
            if score > best_score:
                best_score = score
                best_candidate = cleaned
                
    return cert_no, best_candidate, best_score

def parse_pan_data(text, claim_customer_name):
    # 1. PAN Number
    pan_match = re.search(r'\b[A-Z]{5}[0-9]{4}[A-Z]\b', text, re.IGNORECASE)
    pan_no = pan_match.group(0).upper() if pan_match else None
    
    # 2. DOB
    dob_match = re.search(r'\b\d{2}[-/\.]\d{2}[-/\.]\d{4}\b', text)
    dob = dob_match.group(0) if dob_match else None
    
    # 3. Name Candidates
    name_candidates = []
    # Match Name [NAME] Father's Name
    name_matches = re.finditer(r'Name\s*([A-Za-z\s\.\-]+)\s*(?:Father|\bDOB\b|\bDate\b|\bPermanent\b)', text, re.IGNORECASE)
    for m in name_matches:
        name_candidates.append(clean_extracted_name(m.group(1)))
        
    # Match general: Name: [NAME]
    general_matches = re.finditer(r'(?:Name|NAME)\s*[:\.-]?\s*([A-Za-z\s\.\-]+)', text, re.IGNORECASE)
    for m in general_matches:
        name_candidates.append(clean_extracted_name(m.group(1)))
        
    best_candidate = None
    best_score = 0.0
    for cand in name_candidates:
        if len(cand) < 4:
            continue
        score = fuzz.token_sort_ratio(cand.lower(), claim_customer_name.lower())
        if score > best_score:
            best_score = score
            best_candidate = cand
            
    if best_score < 70:
        lines = [line.strip() for line in re.split(r'[\n,\.:]', text) if len(line.strip()) > 3]
        for line in lines:
            cleaned = clean_extracted_name(line)
            score = fuzz.token_sort_ratio(cleaned.lower(), claim_customer_name.lower())
            if score > best_score:
                best_score = score
                best_candidate = cleaned
                
    return pan_no, dob, best_candidate, best_score

print("--- TESTING LANCY (Claim Name: LANCY BABU P) ---")
c_no, c_name, c_score = parse_cod_data(lancy_disclaimer, "LANCY BABU P")
print(f"Lancy COD Cert No: {c_no}, Name: {c_name} (Fuzzy Score: {c_score})")

p_no, p_dob, p_name, p_score = parse_pan_data(lancy_pan, "LANCY BABU P")
print(f"Lancy PAN No: {p_no}, DOB: {p_dob}, Name: {p_name} (Fuzzy Score: {p_score})")

print("\n--- TESTING RAGHUL (Claim Name: S. RAGHUL SELVAM) ---")
c_no, c_name, c_score = parse_cod_data(raghul_disclaimer, "S. RAGHUL SELVAM")
print(f"Raghul COD Cert No: {c_no}, Name: {c_name} (Fuzzy Score: {c_score})")

p_no, p_dob, p_name, p_score = parse_pan_data(raghul_invoice, "S. RAGHUL SELVAM")
print(f"Raghul PAN No: {p_no}, DOB: {p_dob}, Name: {p_name} (Fuzzy Score: {p_score})")
