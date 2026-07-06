import sys
sys.path.append('c:/Users/admin/Desktop/robbinmahindra')
from scrappage_scheme.invoice_validation import validate_invoice
class MockStore:
    def update_doc_data(self, k, v): pass
claim_details={'Customer Name': 'Bhismadev Dhrua'}
print(validate_invoice(r'c:\Users\admin\Desktop\robbinmahindra\documents\Bhismadev Dhrua\Bhismadev -INV-1782411049764.pdf', claim_details, MockStore()))
