import re
import sys

# Update app_ui.py
try:
    with open(r'c:\Users\admin\Desktop\robbinmahindra\app_ui.py', 'r', encoding='utf-8') as f:
        app_ui_content = f.read()

    new_emoji = '"dealership_name": "🏪 Dealership Name",\n'
    if 'dealership_name' not in app_ui_content:
        app_ui_content = app_ui_content.replace(
            '"welcome_bonus_amount": "🎁 Welcome Bonus",',
            '"welcome_bonus_amount": "🎁 Welcome Bonus",\n            "dealership_name": "🏪 Dealership Name",\n            "document_type": "📑 Document Type",'
        )
        with open(r'c:\Users\admin\Desktop\robbinmahindra\app_ui.py', 'w', encoding='utf-8') as f:
            f.write(app_ui_content)
        print("Updated app_ui.py")
except Exception as e:
    print("Failed to update app_ui.py:", e)

# Update automate_login.py
try:
    with open(r'c:\Users\admin\Desktop\robbinmahindra\automate_login.py', 'r', encoding='utf-8') as f:
        auto_content = f.read()
    
    # We will just replace the "Note:" sections and add "dealership_name" to JSON formats.
    # Replace JSON formats to include dealership_name if not already present
    
    if '"dealership_name": ""' not in auto_content:
        auto_content = auto_content.replace(
            '"company_name": "",',
            '"dealership_name": "",\n"company_name": "",'
        )
        # Bounding boxes addition
        auto_content = auto_content.replace(
            '"chassis_number": [x1, y1, x2, y2],',
            '"chassis_number": [x1, y1, x2, y2],\n  "dealership_name": [x1, y1, x2, y2],\n  "document_type": [x1, y1, x2, y2],'
        )
    
    # Update Note for "document_type"
    auto_content = auto_content.replace(
        '- In "document_type", classify as one of: "PAN", "AADHAAR", "DL", "COD", "DISCLAIMER", "LEDGER", "INVOICE", "GST", or "UNKNOWN".',
        '- In "document_type", classify as Tax Invoice / GST Invoice label, or PAN, AADHAAR, DL, COD, DISCLAIMER, LEDGER.'
    )

    # Add Note for "dealership_name"
    if 'In "dealership_name"' not in auto_content:
        auto_content = auto_content.replace(
            '- In "document_type"',
            '- In "dealership_name", extract the Dealership Name from the heading at the very top.\n- In "document_type"'
        )

    # Update customer_name
    auto_content = auto_content.replace(
        '- In "relation_name"',
        '- In "customer_name", extract the Customer Name exactly as printed in the document.\n- In "relation_name"'
    )

    # Update customer_signature
    if 'In "customer_signature"' not in auto_content:
        auto_content = auto_content.replace(
            '- In "full_text"',
            '- In "customer_signature", determine if Customer Signature is present, and if it matches the printed name. Return True/False or the status.\n- In "full_text"'
        )
        
    # Update invoice_number and invoice_date
    auto_content = auto_content.replace(
        '- In "chassis_number" and "invoice_number"',
        '- In "invoice_number" and "invoice_date", extract GST Invoice Number and GST Invoice Date respectively.\n- In "chassis_number" and "invoice_number"'
    )

    # Update welcome bonus
    auto_content = auto_content.replace(
        '- In "welcome_bonus_amount", specifically look for a note like "Note: Welcome Bonus Amount is Rs.5000.00/- (inclusive of GST)" at the bottom of the invoice and extract this exact amount (e.g. 5000). DO NOT extract the grand total, taxable amount, or discount.',
        '- In "welcome_bonus_amount", extract OEM Loyalty Discount amount or Welcome Bonus Discount amount.'
    )
    
    # Update seal stamp
    auto_content = auto_content.replace(
        '- In "seal_stamp_dealer_name", look carefully for any dealer stamp or company seal in the document. These stamps are commonly circular/round ring shapes with the company name printed along the circular border (curved text around the edge of the circle). They may be blue, purple, or dark ink and may appear faint or overlapping with a signature. Also look for rectangular or oval stamps. Check especially near labels like \'Authorised Signatory\', \'Dealer Seal\', \'Dealer Authorized Person\', or \'Name & Signature along with Dealer Seal\'. Read the company/dealership name from inside or around the stamp border carefully. If no ink stamp is present, also check the document letterhead at the very top for a printed dealer/company name. Only return null if absolutely no company or dealer name can be found anywhere.',
        '- In "seal_stamp_dealer_name", check for Dealership Stamp and Seal — extract the name printed, designation, and reverse charge status.'
    )

    with open(r'c:\Users\admin\Desktop\robbinmahindra\automate_login.py', 'w', encoding='utf-8') as f:
        f.write(auto_content)
    print("Updated automate_login.py")

except Exception as e:
    print("Failed to update automate_login.py:", e)
