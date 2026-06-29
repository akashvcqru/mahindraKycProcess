import sys
sys.path.append(r'c:\Users\admin\Desktop\robbinmahindra')
import automate_login

# Mock the cache
automate_login.OPENAI_CACHE = {
    "dummy_path.pdf": {
        "document_type": "TAX INVOICE",
        "customer_name": "Test Customer",
        "invoice_number": "123456",
        "invoice_date": "2026-06-29"
    }
}

res = automate_login.classify_and_extract(
    "dummy_path.pdf", 
    "TAX INVOICE TEXT", 
    "Test Customer"
)

print("Resulting File Type:", res["file_type"])
assert res["file_type"] == "INVOICE", "Failed: file_type should be INVOICE!"
print("Test Passed: TAX INVOICE successfully normalized to INVOICE")
