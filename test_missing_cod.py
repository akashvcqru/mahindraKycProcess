import json
f = open('ui_history.json', 'r', encoding='utf-8')
data = json.load(f)
issues = [row for row in data if any('Missing Certificate of Deposit' in iss for iss in row.get('issues', []))]
print(f'Found {len(issues)} rows with missing COD.')
if issues:
    print('First one:', issues[0].get('customer_name'))
    print('Documents:', [d['file_name'] for d in issues[0].get('documents', [])])
