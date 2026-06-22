import urllib.request
import csv
import io
import os

def update_scheme_data_from_google_sheet(target_file):
    """Downloads the scheme spreadsheet from Google Sheets as a CSV,
    parses it, and updates the target_file in-place.
    """
    sheet_url = "https://docs.google.com/spreadsheets/d/1TCWi0Xn9fkK2lAsNp0a08gh3TnCbXvFKqmB8eChJuHo/export?format=csv&gid=717771316"
    
    print(f"Fetching Google Sheet CSV from: {sheet_url}")
    req = urllib.request.Request(
        sheet_url, 
        headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
    )
    with urllib.request.urlopen(req, timeout=10) as response:
        content = response.read().decode('utf-8')
        
    reader = csv.reader(io.StringIO(content))
    rows = list(reader)
    
    if not rows:
        raise Exception("Google Sheet returned empty data.")

    welcome_bonus_rows = []
    scrappage_scheme_rows = []
    
    current_section = None
    
    for row in rows:
        if not row:
            continue
        row_str = " ".join(row).lower()
        if "welcome bonus" in row_str:
            current_section = "welcome"
            continue
        elif "scrappage scheme" in row_str:
            current_section = "scrappage"
            continue
            
        if not any(cell.strip() for cell in row):
            current_section = None
            continue
            
        if current_section == "welcome":
            if "brand" in row[0].lower():
                continue
            region = row[7].strip() if len(row) > 7 else ""
            if region and region.lower() not in ["common", "bangalore"]:
                continue
                
            brand = row[0].strip()
            if not brand:
                continue
                
            old_model = row[1].strip() if len(row) > 1 and row[1].strip() else "NA"
            scheme_type = row[2].strip() if len(row) > 2 else ""
            mm_contrib = row[3].strip() if len(row) > 3 else "0"
            dlr_contrib = row[4].strip() if len(row) > 4 else "0"
            total_offer = row[5].strip() if len(row) > 5 else "0"
            credit_note = row[6].strip() if len(row) > 6 else "0"
            
            # Clean newlines from values
            scheme_type = scheme_type.replace("\n", " ").replace("\r", "")
            
            welcome_bonus_rows.append({
                "Brand": brand,
                "Old Vehicle Model": old_model,
                "Scheme Type": scheme_type,
                "M&M Contribution in exchange offer (A)": mm_contrib,
                "Dealer Contribution in exchange offer (B)": dlr_contrib,
                "Total Exchange Offer to the customer (A + B)": total_offer,
                "M&M Credit note to Dealer without GST": credit_note
            })
            
        elif current_section == "scrappage":
            if "brand" in row[0].lower():
                continue
                
            brand = row[0].strip()
            if not brand:
                continue
                
            mm_contrib = row[1].strip() if len(row) > 1 else "0"
            dlr_contrib = row[2].strip() if len(row) > 2 else "0"
            total_scrappage = row[3].strip() if len(row) > 3 else "0"
            credit_note = row[4].strip() if len(row) > 4 else "0"
            
            brand = brand.replace("\n", " ").replace("\r", "")
            
            scrappage_scheme_rows.append({
                "Brand": brand,
                "M&M Contribution (A)": mm_contrib,
                "Dealer Contribution (B)": dlr_contrib,
                "Total Scrappage (A + B)": total_scrappage,
                "Credit Note without GST": credit_note
            })
            
    lines = []
    lines.append("=== WELCOME BONUS (BANGALORE) ===")
    for entry in welcome_bonus_rows:
        lines.append(f"Brand: {entry['Brand']}")
        lines.append(f"Old Vehicle Model: {entry['Old Vehicle Model']}")
        lines.append(f"Scheme Type: {entry['Scheme Type']}")
        lines.append(f"M&M Contribution in exchange offer (A): {entry['M&M Contribution in exchange offer (A)']}")
        lines.append(f"Dealer Contribution in exchange offer (B): {entry['Dealer Contribution in exchange offer (B)']}")
        lines.append(f"Total Exchange Offer to the customer (A + B): {entry['Total Exchange Offer to the customer (A + B)']}")
        lines.append(f"M&M Credit note to Dealer without GST: {entry['M&M Credit note to Dealer without GST']}")
        lines.append("")
        
    lines.append("=== SCRAPPAGE SCHEME (BANGALORE) ===")
    lines.append("Brand | M&M Contribution (A) | Dealer Contribution (B) | Total Scrappage (A + B) | Credit Note without GST")
    for entry in scrappage_scheme_rows:
        mm_c = entry['M&M Contribution (A)'].replace('\n', ' ').strip()
        dlr_c = entry['Dealer Contribution (B)'].replace('\n', ' ').strip()
        tot_s = entry['Total Scrappage (A + B)'].replace('\n', ' ').strip()
        cn_no_gst = entry['Credit Note without GST'].replace('\n', ' ').strip()
        lines.append(f"{entry['Brand']} | {mm_c} | {dlr_c} | {tot_s} | {cn_no_gst}")
        
    lines.append("")
    
    with open(target_file, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"Successfully wrote parsed scheme data to: {target_file}")

# Run dry-run
test_file = "scratch/test_scheme_data.txt"
update_scheme_data_from_google_sheet(test_file)

# Compare test file with the original scheme_data.txt
with open("scheme_data.txt", "r", encoding="utf-8") as f:
    orig = f.read()

with open(test_file, "r", encoding="utf-8") as f:
    generated = f.read()

print("\n--- Differences check ---")
if orig.strip() == generated.strip():
    print("MATCH EXACTLY!")
else:
    print("Mismatches found (this is normal if Google Sheet values differ slightly or have extra items like PICKUP):")
    print(f"Generated text length: {len(generated)}")
    print(f"Original text length: {len(orig)}")
    print("\n--- Original content ---")
    print(orig)
    print("\n--- Generated content ---")
    print(generated)
