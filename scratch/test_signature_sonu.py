import os
import json
import sys
sys.path.append(r'c:\Users\admin\Desktop\robbinmahindra')
import automate_login

pdf_path = r'documents\SONU KUMAR SINGH\Sonu inv-1782379469154.pdf'

# Call verify_document_with_openai_and_portal
res = automate_login.verify_document_with_openai_and_portal(
    pdf_path, {}, {}
)

print("OpenAI verify response:")
print(json.dumps(res, indent=2))
