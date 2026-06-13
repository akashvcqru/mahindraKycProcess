import re
from rapidfuzz import fuzz

lancy_disclaimer = """mahindra VeER MAHINDRA UliT Oaccee Customer Disclaimer for WELCOMEIScrappage Bonus through COD 1, LANCY BABU P , residing at SANDRA VILLA,MARIYAN COLONY KADACHIRA KADACHIRA $ 0, KANNUR,KERALA ,670621, do hereby solemnly affirm and declare as under: state and declare that am the actual and rightful owner/operator of the said Vehicle and have been incontinuous possession, custody, and use of it"""
lancy_pan = """3ir4azr) frtrot HRT RER INCOME TAX DEPARTMENT GOVT OF INDIA rrr cu7G *7d Permanent Account Number Card DQZPP2239C 1354i0  { 70A/ Name LANCY BABU P far #T 7TF / Father's Name LUIS 744iand Date o/ Birth 02/09/1970 TleR / Signature"""

raghul_disclaimer = """u NANT CARS l(glart FiiUTCnoice AA^t:\AMILE AT EVERY MILE hul Selvam , resi red at MYSORE on this 30 of MAy, 2026. ature of Customer: of Customer: S.Raghul Selvam Number: 8660778016 RITANANDAMAYI GO 1 ' I state and declare that I am the actual and rightful owner/operator of the said Vehicle and have been incontinuous possession, custody, and use of it i,tne Vehicl;,rl- o Registration Number: UK0416469 o Vehicle Make: Maruti o Vehicle Model (Not required for Scrappage Case) : Omni oR I am in lawful possession of certificate of Deposit (coD), with number - coD20260440uK0416469 againstRegistration number: uK0416469 (Appricabre onry for ,.rupprg. cases), 2' That the above-mentioned vehicle owned by me/coD has been brought by me to avail Loyalty/scrappagebenefit offered on New M&M vehicre undei the Loyarty/scirppugu program. o New Vehicle Moder: THAR Roxx srAR EDN p AT RWD EWT/BR o Chassis Number: T2E33121 o Engine Number:JWT4E5B975 3. That I undertake and confirm that: o All liabilities in"""
raghul_invoice = """TAX INVOICE +I ANANTCARS AUTO PBIV (Mahindra Authorised Dealer) ATE LIiJIITED .nlTl}# SPORT m tIT I LITY VEHICLES Sales lnvoi@ Karnataka BANK OF BARODA R270177555 S,RAGHUL SELVAM Customer Code: Name: Cust GSTIN: PAN No.l Aadhar No'l Phone Nol Add ress: R270'1 77555 S,RAGHUL SELVAI\,4 FMMP5671 5P xxxxxxxx0048 866077801 6 ]/O G SILAMBU SELVAN, NO"""

def extract_best_name(text, claim_name):
    # Clean and split the text into words, retaining only letters
    cleaned_text = re.sub(r'[^A-Za-z\s]', ' ', text)
    words = [w for w in cleaned_text.split() if len(w) > 0]
    
    claim_words = [w for w in re.sub(r'[^A-Za-z\s]', ' ', claim_name).split() if len(w) > 0]
    n = len(claim_words)
    if n == 0:
        return "", 0.0
        
    best_name = ""
    best_score = 0.0
    
    # Try sliding windows of size n, n+1, and n+2
    for size in [n, n+1, n+2]:
        for i in range(len(words) - size + 1):
            window_words = words[i:i+size]
            candidate = " ".join(window_words)
            # Token sort ratio is perfect here because it's order-independent and handles extra middle names/initials
            score = fuzz.token_sort_ratio(candidate.lower(), claim_name.lower())
            if score > best_score:
                best_score = score
                best_name = candidate
                
    return best_name, best_score

print("--- TESTING SLIDING WINDOW NAME EXTRACTION ---")
for text, name, label in [
    (lancy_disclaimer, "LANCY BABU P", "Lancy Disclaimer"),
    (lancy_pan, "LANCY BABU P", "Lancy PAN"),
    (raghul_disclaimer, "S. RAGHUL SELVAM", "Raghul Disclaimer"),
    (raghul_invoice, "S. RAGHUL SELVAM", "Raghul Invoice")
]:
    extracted, score = extract_best_name(text, name)
    print(f"{label}: Claim Name='{name}' => Extracted='{extracted}' (Score: {score:.2f})")
