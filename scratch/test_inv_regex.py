import re
import sys
import os
from rapidfuzz import fuzz

text = """TAX INVOICE ANANT ANANTCARS AUTo PRIVATE LIMITED CARS SF_Rt Utility VEXELES (Mahindra Authorised Dealer) SMILE AT EVERY MLE Mahindra WWWanantcars com WWW.facebookcom}mahindra.anantcars ANANTCARS AUTO PVT . LTD. NO.64, SBR KEERTHI MALL, KATAMANALLUR GATE, OLD MADRAS ROAD- 560067 Dealer Siaie Code: 29 GST No:] Z3MKCAPEEAKIZR PAN Nc TAX INVOICE (Invoice Issued under Rule 48 of CGSTISOST Rule 2017.) Shlp TolLessse detalls Involce detalls Bill TolLessor detalls R270109-68 Cuetemer Code: Rz70i0e56a GST Involce No: INVZT Yu00i48 Customer Code: HARISH M B Naine; HARISH M B GST Invoice Dale: 31/05/2026 Name: Cust GSTIN: Booklng No:: B-12513950 Cust GSTIN: BZKPE4797G PAN No:: BZHP24797G Bcoklng Date: 27/0412025 PAN No:: No: 5706 Azdhar No:: Aadhar No:: Process Type; Saies Invuice Phone No: 9740 325373 Phone No: 9740325373 232 4TH CRO3S 1ST MAIN Place of Supply: Kamnataka Address: 232 4TH CROSS 1ST MAIN Address: GURUVAREDDY AYOUT A GURUVAREDDTATOUT A Hire Purchase ILeasel Hypo By: BANK OF BARODA NARAYANAPURA BANCALORE; NAFXTANAPURA, BANGALORE, 5p0j6 6o00i6 Branch Name: Kamataka State: Kamiataka State: GST Cess Taxabie Total Amount Sr Product Detaiis HSN Qty Selling Price Discount Amount Rate Amt: Rale Amt  no THARROxx STAR EDN D MT RWD 8101 1228214.29 1222214.29 40 QQ 4912*5.72 1719500.01 EWTIBR VIN: MAIUNZYYZTZE3707S Engine YtT4E6441 Color EVEREST WHITE 1228214.29 0.00 1220214.29 40.0 491285.72 17195.00 Tax Collection at Source 1% 2.01 Round Off 1736685.00 Grand Tolal Rupees Seventeen Lakh Thirty Six Thousand Six Hundred Ninety Five Only Amount in Words at Source under Section 2u6C of Income Tax Act 1961 [s Rs.17425.0 and the total amount payable by customer Is Rs.1736695.01 Note: On thls Invoice Tax Collection ccstiGsT Rata CestiiGst Amt SGSTIUGST Rate SGsTIUGST Amt HSNISAC 20.00 24-642.86 20.00 245042.86 87033291 (4ccossories) (Labour) CgstIIGST Rate 24342.86 SOSTIUGST Rate 245642.86 Total Note Scfappage Bonus Amount is Rs 2000u OO/-(inclusive of GST) Dealer Name: ANANTCARS AUTO PVT. LTD_ Customier Name: HARISH MB Whether tax is Payabie on reverse charges NO IRN Date; IRN Number Want to give a suggeslionor share a feedback abovt dealership experierice? You can re-ch out to Mahindra & Mahindra Ltd Email: cusiomercarem@miatiindta com 24x7 Toll frea: 1801020Y00106 Iers and conditionsk Customer Signature Einvcicing QR Vi Aotised Siguatory SER KPura Behgeturu CIN No. u501O2KAZO1ZPTCO66014 GSTIN 29AAKCA96?4KIZR BG Ruad #5 R40, Sy No.10, Mi ii Ruati #37 1, Sai-$ (Maraitiaiialli) #60 R.J Gwviki KR. Puamn # 401 H_kolc : SDRR-Iti Mall Jallaidhna "PARAMDHAN" , Nexi io BHEL, Quii Ruail Opp EZurie Club, Kunfara Siicci Main Ruii, Sy No. 77 , Kiaaallur Villag Onn. Raiiiuw Hu-ital Qpp. Indian Oii Fcivui Bunk; Arlaiidriallar; Ctilhm arla Halli; Old Maiiaz Zid Biiaalialli Hili Bilakajialli; Balln gilaiia Runtl, Mysint Ruau Maiaiilaiialli, Briujaluru - 5nW37. KR: Puram; Husakic; Talik Brujaluru - 5614'76. Erugaluru - S60 426_ Land Mark Nexi iu Dqviit = Pizza Brnaluru _ Sho (136 Rr.Hluru Snii 4i9 Key 3 1 Twer; Riny"""

claim_customer_name = "HARISH M B"

# 1. Name Extraction
best_extracted_name, best_name_score = None, 0.0
# Look for HARISH M B
sys.path.append(os.getcwd())
from automate_login import extract_best_name, clean_extracted_name
best_extracted_name, best_name_score = extract_best_name(text, claim_customer_name)

name_match = re.search(r'\b(?:Customer\s+)?N[la]me\s*[:\.-]?\s*([A-Z\s\.\-]+)', text, re.IGNORECASE)
extracted_name = None
name_score = 0.0
if name_match:
    extracted_name = clean_extracted_name(name_match.group(1))
    name_score = fuzz.token_sort_ratio(extracted_name.lower(), claim_customer_name.lower())

if best_name_score > name_score:
    extracted_name = best_extracted_name
    name_score = best_name_score

print(f"Extracted Customer Name: {extracted_name} (Score: {name_score})")

# 2. Dealership Name
dealer_match = re.search(r'\b([A-Z0-9\s\.\-]+(?:PVT\.?\s*LTD\.?|PRIVATE\s+LIMITED|LTD\.?))\b', text, re.IGNORECASE)
dealer_name = dealer_match.group(1).strip() if dealer_match else None
if dealer_name:
    dealer_name = re.sub(r'^(?:TAX\s+INVOICE|GST\s+INVOICE|BILL\s+TO|SHIP\s+TO)\s*', '', dealer_name, flags=re.IGNORECASE).strip()
print(f"Extracted Dealer Name: {dealer_name}")

# 3. Invoice No
inv_no = None
inv_no_match = re.search(r'GST\s*Invo[a-z]*\s*No\s*[:\.-]?\s*([A-Z0-9\s/]+)', text, re.IGNORECASE)
if inv_no_match:
    raw_inv = inv_no_match.group(1).strip()
    clean_tokens = []
    for token in raw_inv.split():
        if token.lower() in ["customer", "code", "date", "booking", "name", "gstin"]:
            break
        clean_tokens.append(token)
    inv_no = "".join(clean_tokens)
print(f"Extracted Invoice No: {inv_no}")

# 4. Invoice Date
inv_date_match = re.search(r'GST\s*Invo[a-z]*\s*Da[a-z]*\s*[:\.-]?\s*(\d{2}[-/\.]\d{2}[-/\.]\d{4})', text, re.IGNORECASE)
inv_date = inv_date_match.group(1).strip() if inv_date_match else None
print(f"Extracted Invoice Date: {inv_date}")

# 5. Bonus Amount Extraction (Fuzzy check for scrappage/welcome bonus)
amt_match = re.search(
    r'(?:sc[fa]ppage|welcome|loyalty|exchange|bonus)\s+(?:bonus\s+)?(?:amount\s+)?(?:is\s+)?(?:rs\.?\s*)?([A-Z0-9a-z\.,\s/-]+)',
    text.upper(),
    re.IGNORECASE
)
invoice_amount = None
if amt_match:
    match_str = amt_match.group(1).upper()
    print(f"Raw matched amount string: {match_str}")
    for char, replacement in [
        ('O', '0'), ('U', '0'), ('I', '1'), ('L', '1'), ('S', '5'), ('B', '8'), ('Z', '2'), ('G', '6'),
        ('o', '0'), ('u', '0'), ('i', '1'), ('l', '1'), ('s', '5'), ('b', '8'), ('z', '2'), ('g', '6')
    ]:
        match_str = match_str.replace(char, replacement)
    
    tokens = [t.strip('.-/') for t in re.split(r'[^0-9\.]', match_str) if t.strip('.-/')]
    print(f"Cleaned tokens: {tokens}")
    for t in tokens:
        try:
            val = float(t)
            if val >= 1000.0:
                invoice_amount = val
                break
        except ValueError:
            pass

print(f"Extracted Invoice Amount: {invoice_amount}")

# 6. Test dealership matching function
def normalize_str(s):
    if not s:
        return ""
    return re.sub(r'[^A-Z0-9]', '', s.upper())

def compare_dealership_names(doc_dealer, web_dealer):
    if not doc_dealer or not web_dealer:
        return False
    doc_norm = normalize_str(doc_dealer)
    web_norm = normalize_str(web_dealer)
    
    if doc_norm == web_norm:
        return True
        
    def standardize_dealer(s):
        s = s.replace("PRIVATELIMITED", "PVTLTD").replace("PRIVATE", "PVT").replace("LIMITED", "LTD")
        return s
        
    if standardize_dealer(doc_norm) == standardize_dealer(web_norm):
        return True
        
    score = fuzz.token_sort_ratio(doc_dealer.lower(), web_dealer.lower())
    if score >= 70:
        return True
        
    web_words = [w for w in re.sub(r'[^A-Z0-9]', ' ', web_dealer.upper()).split() if len(w) > 3 and w not in ["AUTO", "PVT", "LTD", "PRIVATE", "LIMITED", "GARAGE", "INDIA"]]
    if web_words:
        first_unique = web_words[0]
        if first_unique in doc_norm:
            return True
            
    return False

web_dealer_1 = "ANANTCARS AUTO PVT. LTD."
print(f"Match results (should be True): {compare_dealership_names(dealer_name, web_dealer_1)}")
