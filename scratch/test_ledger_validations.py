import re

# Simple mock functions to match what's in automate_login.py
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

def validate_ledger_conditions(text, filename, claim_details, current_zone, current_city, claim_choice):
    issues = []
    text_upper = text.upper()
    lines = text.split("\n")
    
    zone = current_zone.strip().upper() if current_zone else "COMMON"
    city = current_city.strip().upper() if current_city else "COMMON"
    
    is_loyalty = (claim_choice == "1" or claim_choice == 1 or claim_choice == "loyalty")
    
    # Extract dashboard amounts
    total_amount_gst = None
    claim_amount_no_gst = None
    approval_amount = None
    
    for k, v in claim_details.items():
        norm_k = k.lower()
        if "total amount" in norm_k and "approved" not in norm_k:
            try:
                total_amount_gst = float(''.join(c for c in v if c.isdigit() or c == '.'))
            except Exception:
                pass
        if "claim amount" in norm_k:
            try:
                claim_amount_no_gst = float(''.join(c for c in v if c.isdigit() or c == '.'))
            except Exception:
                pass
        if "approved total amount" in norm_k or "approval total amount" in norm_k or "approved amount" in norm_k:
            if "dealer" not in norm_k:
                try:
                    approval_amount = float(''.join(c for c in v if c.isdigit() or c == '.'))
                except Exception:
                    pass

    print(f"--- Running Validation for Zone: {zone}, City: {city}, Type: {'Loyalty' if is_loyalty else 'Exchange/Scrappage'} ---")
    print(f"Dashboard values - Approval: {approval_amount}, Total (GST): {total_amount_gst}, Claim (No GST): {claim_amount_no_gst}")

    # Condition 1: loyalty/east/Raipur, Bhubaneswar, Patna
    if is_loyalty and zone == "EAST" and city in ["RAIPUR", "BHUBANESWAR", "PATNA"]:
        welcome_found = False
        welcome_amt_match = False
        extracted_welcome_amt = None
        
        for line in lines:
            line_norm = line.upper().replace("WELCOMC", "WELCOME").replace("WELCONE", "WELCOME")
            if "WELCOME" in line_norm and "BONUS" in line_norm:
                welcome_found = True
                floats = find_floats_in_line(line)
                if floats:
                    extracted_welcome_amt = floats[0]
                    compare_targets = [val for val in [approval_amount, total_amount_gst, claim_amount_no_gst] if val is not None]
                    for target in compare_targets:
                        if abs(extracted_welcome_amt - target) < 2.0:
                            welcome_amt_match = True
                            break
                            
        if not welcome_found:
            issues.append(f"Ledger [{filename}]: 'Welcome Bonus' not found in ledger (Required for East Zone / {city})")
        elif not welcome_amt_match:
            issues.append(f"Ledger [{filename}]: Welcome Bonus amount mismatch in ledger. Extracted: {extracted_welcome_amt}, Dashboard expected: {approval_amount or total_amount_gst or 'Not Found'}")

    # Condition 1.5: North Zone checks ("Welcome Bonus", "Loyalty Bonus", "Exchange", "Scrappage")
    if zone == "NORTH":
        north_kws = ["WELCOME BONUS", "LOYALTY BONUS", "EXCHANGE", "SCRAPPAGE"]
        found_north_entry = False
        north_amt_match = False
        extracted_north_amt = None
        
        for line in lines:
            line_norm = line.upper().replace("WELCOMC", "WELCOME").replace("WELCONE", "WELCOME")
            matched_kw = None
            for kw in north_kws:
                if kw in line_norm:
                    matched_kw = kw
                    break
            if matched_kw:
                found_north_entry = True
                floats = find_floats_in_line(line)
                if floats:
                    extracted_north_amt = floats[0]
                    compare_targets = [val for val in [approval_amount, total_amount_gst, claim_amount_no_gst] if val is not None]
                    for target in compare_targets:
                        if abs(extracted_north_amt - target) < 2.0:
                            north_amt_match = True
                            break
        if found_north_entry and not north_amt_match:
            issues.append(f"Ledger [{filename}]: North Zone entry amount mismatch in ledger. Extracted: {extracted_north_amt}, Dashboard expected: {approval_amount or total_amount_gst or 'Not Found'}")

    # Condition 1.7: West Zone checks ("green bonus", "scrappage", "loyalty bonus", "scheme 18%")
    if zone == "WEST":
        west_kws = ["GREEN BONUS", "SCRAPPAGE", "LOYALTY BONUS", "SCHEME 18%"]
        found_west_entry = False
        west_amt_match = False
        extracted_west_amt = None
        
        for line in lines:
            line_norm = line.upper().replace("WELCOMC", "WELCOME").replace("WELCONE", "WELCOME")
            matched_kw = None
            for kw in west_kws:
                if kw in line_norm:
                    matched_kw = kw
                    break
            if matched_kw:
                found_west_entry = True
                # Clean percentage values like "18%"
                line_clean = re.sub(r'\d+\s*%', '', line)
                floats = find_floats_in_line(line_clean)
                if floats:
                    extracted_west_amt = floats[0]
                    compare_targets = [val for val in [approval_amount, total_amount_gst, claim_amount_no_gst] if val is not None]
                    for target in compare_targets:
                        if abs(extracted_west_amt - target) < 2.0:
                            west_amt_match = True
                            break
        if found_west_entry and not west_amt_match:
            issues.append(f"Ledger [{filename}]: West Zone entry amount mismatch in ledger. Extracted: {extracted_west_amt}, Dashboard expected: {approval_amount or total_amount_gst or 'Not Found'}")

    # General Scrappage check (any zone): match with/without GST
    scrappage_found = False
    scrappage_amt_match = False
    extracted_scrappage_amt = None
    
    for line in lines:
        line_norm = line.upper()
        if "SCRAPPAGE" in line_norm and "BONUS" in line_norm:
            scrappage_found = True
            floats = find_floats_in_line(line)
            if floats:
                extracted_scrappage_amt = floats[0]
                compare_targets = [val for val in [approval_amount, total_amount_gst, claim_amount_no_gst] if val is not None]
                for target in compare_targets:
                    if abs(extracted_scrappage_amt - target) < 2.0:
                        scrappage_amt_match = True
                        break

    # Scrappage amount validation if found
    if scrappage_found and extracted_scrappage_amt is not None and not scrappage_amt_match:
        issues.append(f"Ledger [{filename}]: Scrappage Bonus amount mismatch in ledger. Extracted: {extracted_scrappage_amt}, Dashboard expected: {approval_amount or total_amount_gst or 'Not Found'}")

    # Condition 2: in East and South, if "SCRAPPAGE BONUS" or "Welcomc Bonus" not found in ledger, hold it
    if zone in ["EAST", "SOUTH"]:
        if is_loyalty:
            welcome_found = False
            for line in lines:
                line_norm = line.upper().replace("WELCOMC", "WELCOME").replace("WELCONE", "WELCOME")
                if "WELCOME" in line_norm and "BONUS" in line_norm:
                    welcome_found = True
                    break
            if not welcome_found:
                issues.append(f"Ledger [{filename}]: 'Welcome Bonus' not found in ledger (Required for {zone} Zone)")
        else:
            if not scrappage_found:
                issues.append(f"Ledger [{filename}]: 'Scrappage Bonus' not found in ledger (Required for {zone} Zone)")
                
    return issues

# Test Scenarios
# Scenario A: Loyalty, East, Patna. Ledger contains Welcome Bonus of 15000. Dashboard approved total is 15000.
claim_a = {"Approved Total Amount": "15000", "Total Amount": "17700", "Claim Amount": "15000"}
text_a = "2026-06-20 Welcome Bonus payment: 15000\nSome other narration: 500"
res_a = validate_ledger_conditions(text_a, "LEDGER-A.pdf", claim_a, "East", "Patna", "loyalty")
print(f"Result A (Should be empty list): {res_a}\n")

# Scenario B: Loyalty, East, Patna. Ledger Welcome Bonus amount is 10000. Dashboard expected is 15000.
text_b = "2026-06-20 Welcomc Bonus payment: 10000\nSome other narration: 500"
res_b = validate_ledger_conditions(text_b, "LEDGER-B.pdf", claim_a, "East", "Patna", "loyalty")
print(f"Result B (Should have amount mismatch issue): {res_b}\n")

# Scenario C: Loyalty, South, Bangalore. Welcomc Bonus is missing.
text_c = "2026-06-20 Other payment: 15000\nSome other narration: 500"
res_c = validate_ledger_conditions(text_c, "LEDGER-C.pdf", claim_a, "South", "Bangalore", "loyalty")
print(f"Result C (Should have Welcome Bonus missing issue): {res_c}\n")

# Scenario D: Exchange/Scrappage, East, Raipur. Ledger has SCRAPPAGE BONUS 20000. Dashboard Total Amount with GST is 23600, Claim Amount without GST is 20000.
claim_d = {"Approved Total Amount": "20000", "Total Amount": "23600", "Claim Amount": "20000"}
text_d = "2026-06-20 Scrappage Bonus paid: 20000\nOther details"
res_d = validate_ledger_conditions(text_d, "LEDGER-D.pdf", claim_d, "East", "Raipur", "exchange")
print(f"Result D (Should be empty list - matches without GST): {res_d}\n")

# Scenario E: Exchange/Scrappage, East, Raipur. Ledger has SCRAPPAGE BONUS 23600.
text_e = "2026-06-20 Scrappage Bonus paid: 23600\nOther details"
res_e = validate_ledger_conditions(text_e, "LEDGER-E.pdf", claim_d, "East", "Raipur", "exchange")
print(f"Result E (Should be empty list - matches with GST): {res_e}\n")

# Scenario F: Exchange/Scrappage, South. SCRAPPAGE BONUS is missing.
text_f = "2026-06-20 Some other entry: 20000"
res_f = validate_ledger_conditions(text_f, "LEDGER-F.pdf", claim_d, "South", "Chennai", "exchange")
print(f"Result F (Should have Scrappage Bonus missing issue): {res_f}\n")

# Scenario G: North Zone, Exchange, correct Scrappage entry amount 20000
text_g = "2026-06-20 Scrappage entry: 20000"
res_g = validate_ledger_conditions(text_g, "LEDGER-G.pdf", claim_d, "North", "Delhi", "exchange")
print(f"Result G (Should be empty list): {res_g}\n")

# Scenario H: North Zone, Exchange, incorrect Scrappage entry amount 12000
text_h = "2026-06-20 Scrappage entry: 12000"
res_h = validate_ledger_conditions(text_h, "LEDGER-H.pdf", claim_d, "North", "Delhi", "exchange")
print(f"Result H (Should have North Zone entry amount mismatch issue): {res_h}\n")

# Scenario I: West Zone, Exchange, correct "scheme 18%" amount 20000
text_i = "2026-06-20 scheme 18% paid: 20000"
res_i = validate_ledger_conditions(text_i, "LEDGER-I.pdf", claim_d, "West", "Mumbai", "exchange")
print(f"Result I (Should be empty list): {res_i}\n")

# Scenario J: West Zone, Exchange, incorrect "green bonus" amount 15000
text_j = "2026-06-20 green bonus paid: 15000"
res_j = validate_ledger_conditions(text_j, "LEDGER-J.pdf", claim_d, "West", "Mumbai", "exchange")
print(f"Result J (Should have West Zone entry amount mismatch issue): {res_j}\n")
