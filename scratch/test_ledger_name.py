import re
from rapidfuzz import fuzz

def new_extract_best_name(text, claim_name):
    # Split text by whitespace first
    raw_tokens = text.split()
    filtered_words = []
    for token in raw_tokens:
        letters = sum(1 for c in token if c.isalpha())
        digits = sum(1 for c in token if c.isdigit())
        # Skip reference codes, dates, transaction IDs, etc.
        if digits >= 3 or (digits > 0 and digits >= letters):
            continue
        cleaned = re.sub(r'[^A-Za-z]', '', token)
        if cleaned:
            filtered_words.append(cleaned)
            
    claim_words = [w for w in re.sub(r'[^A-Za-z\s]', ' ', claim_name).split() if len(w) > 0]
    n = len(claim_words)
    if n == 0:
        return "", 0.0
        
    best_name = ""
    best_score = 0.0
    
    # Check window sizes from max(1, n-1) to n+2
    min_size = max(1, n - 1)
    max_size = n + 2
    
    for size in range(min_size, max_size + 1):
        for i in range(len(filtered_words) - size + 1):
            window_words = filtered_words[i:i+size]
            candidate = " ".join(window_words)
            
            cand_clean = candidate.replace(" ", "").lower()
            claim_clean = claim_name.replace(" ", "").lower()
            score = fuzz.ratio(cand_clean, claim_clean)
            
            if score > best_score:
                best_score = score
                best_name = candidate
                
    return best_name, best_score

# Test cases
tests = [
    {
        "name": "G NIVETHA",
        "text": "Wens Cusloner Nare Assigument Journal Enlry Dale Joural Entry Joumal Type Amount (CoCode Narralion Reference Reference NIVETHA 12.06.2026 2024108819 SU 959,557,00 INR R270096233 NIVETHA 12.06.2026"
    },
    {
        "name": "LANCY BABU P",
        "text": "Mahindra VEER Mk TOWER PODIKKUNDU KANNUR KERALA 670004 STATEMENT OF ACCOUNT GST NO 32AFYPV741JB2Z7 VEER 15.58 48 PODIRKUNDU 13/06/2026 From 01/04/2026 To 13/06/2026 LANCY BABU F SANDRA VILLA MARIYAN KADACHIRA"
    },
    {
        "name": "SRaghul Selvam",
        "text": "Date Reference Narration Amount 29.05.2026 2613400622 Loyalty -20,000.00 INR Customer Name S RAGHUL SELVAM Account No 12345"
    }
]

for t in tests:
    extracted, score = new_extract_best_name(t["text"], t["name"])
    print(f"Claim Name: '{t['name']}' -> Extracted: '{extracted}', Score: {score:.2f}%")
