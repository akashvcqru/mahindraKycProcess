import os
import json
import sys
sys.path.append(r'c:\Users\admin\Desktop\robbinmahindra')
import automate_login

pdf_path = r'documents\SONU KUMAR SINGH\Sonu inv-1782379469154.pdf'

# Call extract_details_via_openai
res = automate_login.extract_details_via_openai(
    pdf_path
)

print("OpenAI extract response:")
print(json.dumps(res, indent=2))
