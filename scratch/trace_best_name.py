from rapidfuzz import fuzz
import re

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
            # Remove spaces to be robust to spacing differences (like "S Raghul" vs "SRaghul")
            cand_clean = candidate.replace(" ", "").lower()
            claim_clean = claim_name.replace(" ", "").lower()
            score = fuzz.ratio(cand_clean, claim_clean)
            print(f"Size {size}, Candidate: '{candidate}' => Spaceless Score: {score:.1f}%")
            if score > best_score:
                best_score = score
                best_name = candidate
                
    return best_name, best_score

text = 'HTTTRTT Government of India 3TTT @)a\' Odrbej 1 S.Raghul Selvam "70J346Wniy s1 Dooa\' / DOB: 07/04/1993 3 dda / Male 2 9629 3346 0048 TT 3HR , # 4uat Royo'
claim_name = "SRaghul Selvam"
print(extract_best_name(text, claim_name))
