import re
from rapidfuzz import fuzz

lancy_disclaimer = """mahindra VeER MAHINDRA UliT Oaccee Customer Disclaimer for WELCOMEIScrappage Bonus through COD 1, LANCY BABU P , residing at SANDRA VILLA,MARIYAN COLONY KADACHIRA KADACHIRA $ 0, KANNUR,KERALA ,670621, do hereby solemnly affirm and declare as under: state and declare that am the actual and rightful ownerioperator of the said Vehicle and have been in continuous possession, custody, and use of it ("the Vehicle" ); Registration Number: DOZPP2239C Vehicle Make Others Vehicle Model (Not required for Scrappage Case) Others OR |am in Iawful possession of Certificate of Deposit (COD), with number against Registration number; DQZPP2239C (Applicable only for scrappage cases) That the above-mentioned Vehicle Owned by meICOD has been brought by me to avail WELCOMEIscrappage benefit offered on New M&M Vehicle under the WELCOMEIScrappage Program; Vehicle Model; VEERO | SXXL SD V6 Chassis Number: T6E16867 Engine Number: CUT6E54827 Neither VEER nor Mahindra & Mahindra Ltd shall be held liable or responsible in any manner for any past or future claimsIdisputes relating to the Vehicle or COD hereby indemnify and keep harmless VEER; Mahindra & Mahindra Ltd, its dealers, agents, and representatives from any legal, financial, or other liability arising out of the Vehicle or COD prior t0 the date of Scrappage benefit Basis above, have availed and received WELCOME / Scrappage Benefit of INR 15000 0 from the VEER affirm  that will not  Trade / Sell the COD used for Scrappage Benefit  associated with the Reg No DOZPP2239C with anyone hereby declare that this statement is made voluntarily by me; without any coercion , pressure, or undue influence from any party. It is intended solely to facilitate the WELCOME / COD based scrappage transaction and shall be binding upon me; my heirs, successors, and assigns Declared at KANNUR on this 10 of JUNE; 2026. Signature of Customer: Name of Customer: LANCY BABU P Contact Number 9895876324 VEER Mk Tower Podikundu PO Pallikunnu Kannur; Korala 670 004 291 49/ 297 6902 WWW veermahindra com Po: New
CUSTOMER DISCLAIMER DATE: [0/06/2026 confirm that | have availed Weleome Bonus of Rs.15,000/- from the dealership name VEER for buying of new Vehicle Model VEERO LSXXL SD V6 Chassis no: MAIUVZCUXTGEA6867 Engine no: CUT6E54827 Invoice no: INV27A000T26 Invoice 31/05/2026 KAn Dealer Authorized Person Customer Signature FR 8 Akhilesh 7309 LANCY BABU P 9895876324 Date: UNDu;"""

raghul_disclaimer = """u NANT CARS l(glart FiiUTCnoice AA^t:\AMILE AT EVERY MILE hul Selvam , resi red at MYSORE on this 30 of MAy, 2026. ature of Customer: of Customer: S.Raghul Selvam Number: 8660778016 RITANANDAMAYI GO 1 ' I state and declare that I am the actual and rightful owner/operator of the said Vehicle and have been incontinuous possession, custody, and use of it i,tne Vehicl;,rl- o Registration Number: UK0416469 o Vehicle Make: Maruti o Vehicle Model (Not required for Scrappage Case) : Omni oR I am in lawful possession of certificate of Deposit (coD), with number - coD20260440uK0416469 againstRegistration number: uK0416469 (Appricabre onry for ,.rupprg. cases), 2' That the above-mentioned vehicle owned by me/coD has been brought by me to avail Loyalty/scrappagebenefit offered on New M&M vehicre undei the Loyarty/scirppugu program. o New Vehicle Moder: THAR Roxx srAR EDN p AT RWD EWT/BR o Chassis Number: T2E33121 o Engine Number:JWT4E5B975 3. That I undertake and confirm that: o All liabilities in"""

def extract_best_name(text, claim_name):
    cleaned_text = re.sub(r'[^A-Za-z\s]', ' ', text)
    words = [w for w in cleaned_text.split() if len(w) > 0]
    claim_words = [w for w in re.sub(r'[^A-Za-z\s]', ' ', claim_name).split() if len(w) > 0]
    n = len(claim_words)
    if n == 0:
        return "", 0.0
    best_name = ""
    best_score = 0.0
    for size in [n, n+1, n+2]:
        for i in range(len(words) - size + 1):
            window_words = words[i:i+size]
            candidate = " ".join(window_words)
            score = fuzz.token_sort_ratio(candidate.lower(), claim_name.lower())
            if score > best_score:
                best_score = score
                best_name = candidate
    return best_name, best_score

def parse_disclaimer_data(text, claim_customer_name):
    # 1. Registration Number (Old vehicle)
    reg_match = re.search(r'Registration\s*Number\s*[:;-]?\s*([A-Z0-9]+)', text, re.IGNORECASE)
    reg_no = reg_match.group(1).strip() if reg_match else None
    if not reg_no:
        reg_match2 = re.search(r'Reg\s*No\s*[:;-]?\s*([A-Z0-9]+)', text, re.IGNORECASE)
        reg_no = reg_match2.group(1).strip() if reg_match2 else None
    if not reg_no:
        reg_match3 = re.search(r'against\s*Registration\s*number\s*[:;]?\s*([A-Z0-9]+)', text, re.IGNORECASE)
        reg_no = reg_match3.group(1).strip() if reg_match3 else None

    # 2. Vehicle Make
    make_match = re.search(r'Vehicle\s*Make\s*[:;-]?\s*([A-Za-z0-9\s]+?)(?=\s+Vehicle|\s+OR|\s+That|\bEngine\b|\n|$)', text, re.IGNORECASE)
    make = make_match.group(1).strip() if make_match else None

    # 3. Vehicle Model (Old)
    old_model_match = re.search(r'Vehicle\s*Model\s*\(Not\s*required\s*for\s*Scrappage\s*Case\)\s*[:;-]?\s*([A-Za-z0-9\s]+?)(?=\s+OR|\s+That|\bEngine\b|\n|$)', text, re.IGNORECASE)
    old_model = old_model_match.group(1).strip() if old_model_match else None

    # 4. New Vehicle Model
    new_model_match = re.search(r'New\s*Vehicle\s*Mode[lr]\s*[:;-]?\s*([A-Za-z0-9\s|/-]+?)(?=\s+Chassis|\s+Engine|\s+That|\n|$)', text, re.IGNORECASE)
    new_model = new_model_match.group(1).strip() if new_model_match else None
    if not new_model:
        new_model_match2 = re.search(r'buying\s*of\s*new\s*Vehicle\s*Model\s*([A-Za-z0-9\s|/-]+?)(?=\s+Chassis|\s+Engine|\s+Invoice|\n|$)', text, re.IGNORECASE)
        new_model = new_model_match2.group(1).strip() if new_model_match2 else None
    if not new_model:
        new_model_match3 = re.search(r'Vehicle\s*Model\s*;\s*([A-Za-z0-9\s|/-]+?)(?=\s+Chassis|\s+Engine|\s+That|\n|$)', text, re.IGNORECASE)
        new_model = new_model_match3.group(1).strip() if new_model_match3 else None

    # 5. Chassis Number
    chassis_matches = re.findall(r'Chassis\s*(?:Number|no)\s*[:;-]?\s*([A-Z0-9]+)', text, re.IGNORECASE)
    chassis = None
    if chassis_matches:
        chassis = max(chassis_matches, key=len)

    # 6. Customer Name
    extracted_name, name_score = extract_best_name(text, claim_customer_name)

    return {
        "Registration Number": reg_no,
        "Vehicle Make": make,
        "Old Vehicle Model": old_model,
        "New Vehicle Model": new_model,
        "Chassis Number": chassis,
        "Customer Name": extracted_name,
        "Name Match Score": name_score
    }

print("=== LANCY ===")
import json
print(json.dumps(parse_disclaimer_data(lancy_disclaimer, "LANCY BABU P"), indent=2))

print("\n=== RAGHUL ===")
print(json.dumps(parse_disclaimer_data(raghul_disclaimer, "S. RAGHUL SELVAM"), indent=2))
