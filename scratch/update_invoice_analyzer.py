import re

with open(r'c:\Users\admin\Desktop\robbinmahindra\invoice_analyzer.html', 'r', encoding='utf-8') as f:
    content = f.read()

# Extract CROPS and PDF_B64 using regex
crops_match = re.search(r'const CROPS = \[.*?\];', content, flags=re.DOTALL)
pdf_match = re.search(r'const PDF_B64 = \".*?\";', content, flags=re.DOTALL)

if not crops_match or not pdf_match:
    print("Could not find CROPS or PDF_B64 arrays")
    exit(1)

crops_str = crops_match.group(0)
pdf_str = pdf_match.group(0)

new_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Tax Invoice Analyzer</title>
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');
:root {{
  --bg-color: #0f172a;
  --surface: rgba(30, 41, 59, 0.7);
  --border: rgba(255, 255, 255, 0.1);
  --text-primary: #f8fafc;
  --text-secondary: #94a3b8;
  --accent-1: #3b82f6;
  --accent-2: #8b5cf6;
  --success: #10b981;
}}
* {{ box-sizing: border-box; margin: 0; padding: 0; }}
body {{ 
  font-family: 'Inter', sans-serif; 
  background: var(--bg-color); 
  color: var(--text-primary); 
  min-height: 100vh;
  padding: 2rem;
  background-image: radial-gradient(circle at top right, rgba(59, 130, 246, 0.1), transparent 40%),
                    radial-gradient(circle at bottom left, rgba(139, 92, 246, 0.1), transparent 40%);
}}
.app {{ max-width: 900px; margin: 0 auto; }}
.header {{ margin-bottom: 2rem; text-align: center; }}
.header h2 {{ font-size: 28px; font-weight: 700; background: -webkit-linear-gradient(45deg, var(--accent-1), var(--accent-2)); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }}
.header p {{ font-size: 15px; color: var(--text-secondary); margin-top: 8px; }}
.prompt-box {{ 
  background: var(--surface); 
  border: 1px solid var(--border); 
  border-radius: 16px; 
  padding: 1.5rem; 
  margin-bottom: 2rem;
  backdrop-filter: blur(12px);
  box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06);
}}
.prompt-box h3 {{ font-size: 14px; font-weight: 600; color: var(--text-secondary); text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 12px; display: flex; justify-content: space-between; align-items: center; }}
.prompt-text {{ 
  font-family: monospace; 
  font-size: 13px; 
  color: #e2e8f0; 
  line-height: 1.7; 
  white-space: pre-wrap; 
  background: rgba(0,0,0,0.3);
  padding: 1rem;
  border-radius: 8px;
  border: 1px solid rgba(255,255,255,0.05);
}}
.copy-btn {{ 
  font-size: 13px; padding: 6px 12px; border: 1px solid var(--border); border-radius: 6px; 
  background: rgba(255,255,255,0.05); color: var(--text-primary); cursor: pointer; transition: all 0.2s ease;
}}
.copy-btn:hover {{ background: rgba(255,255,255,0.1); }}
.run-btn {{ 
  display: flex; justify-content: center; align-items: center; gap: 8px;
  width: 100%; padding: 14px; font-size: 16px; font-weight: 600; 
  border: none; border-radius: 12px; 
  background: linear-gradient(135deg, var(--accent-1), var(--accent-2)); 
  color: white; cursor: pointer; margin-bottom: 2rem;
  transition: transform 0.2s ease, box-shadow 0.2s ease;
  box-shadow: 0 10px 15px -3px rgba(59, 130, 246, 0.3);
}}
.run-btn:hover {{ transform: translateY(-2px); box-shadow: 0 10px 25px -3px rgba(59, 130, 246, 0.5); }}
.run-btn:disabled {{ opacity: 0.7; cursor: not-allowed; transform: none; box-shadow: none; }}
.status {{ 
  font-size: 14px; color: var(--accent-1); text-align: center; margin-bottom: 2rem; display: none; 
  animation: pulse 2s cubic-bezier(0.4, 0, 0.6, 1) infinite;
}}
@keyframes pulse {{ 0%, 100% {{ opacity: 1; }} 50% {{ opacity: .5; }} }}
.results {{ display: none; animation: fadeIn 0.5s ease-out; }}
@keyframes fadeIn {{ from {{ opacity: 0; transform: translateY(10px); }} to {{ opacity: 1; transform: translateY(0); }} }}
.section-title {{ font-size: 12px; font-weight: 600; letter-spacing: 0.1em; text-transform: uppercase; color: var(--text-secondary); margin: 2rem 0 1rem; border-bottom: 1px solid var(--border); padding-bottom: 8px; }}
.card {{ 
  background: var(--surface); border: 1px solid var(--border); border-radius: 16px; 
  overflow: hidden; margin-bottom: 1.5rem; backdrop-filter: blur(12px);
  transition: transform 0.3s ease;
}}
.card:hover {{ transform: translateY(-4px); border-color: rgba(255,255,255,0.2); }}
.card-header {{ padding: 1rem 1.25rem; border-bottom: 1px solid var(--border); display: flex; align-items: center; gap: 12px; background: rgba(0,0,0,0.2); }}
.card-num {{ width: 28px; height: 28px; border-radius: 50%; background: linear-gradient(135deg, var(--accent-1), var(--accent-2)); color: white; font-size: 13px; font-weight: 600; display: flex; align-items: center; justify-content: center; flex-shrink: 0; box-shadow: 0 2px 4px rgba(0,0,0,0.2); }}
.card-label {{ font-size: 16px; font-weight: 500; color: var(--text-primary); }}
.card-img {{ width: 100%; display: block; border-bottom: 1px solid var(--border); }}
.card-detail {{ padding: 1.25rem; }}
.detail-field {{ font-size: 12px; color: var(--text-secondary); text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 6px; }}
.detail-value {{ font-size: 15px; color: var(--text-primary); font-weight: 500; line-height: 1.5; }}
.ai-section {{ margin-top: 12px; padding-top: 12px; border-top: 1px dashed rgba(255,255,255,0.1); }}
.ai-label {{ display: inline-flex; align-items: center; gap: 4px; font-size: 11px; padding: 4px 10px; border-radius: 20px; background: rgba(16, 185, 129, 0.2); color: var(--success); font-weight: 600; border: 1px solid rgba(16, 185, 129, 0.3); }}
.ai-value {{ font-size: 15px; color: #fff; margin-top: 8px; border-left: 3px solid var(--success); padding-left: 12px; line-height: 1.6; }}
</style>
</head>
<body>
<div class="app">
  <div class="header">
    <h2>Tax Invoice Vision Analyzer</h2>
    <p>Premium document extraction using OpenAI GPT-4 Vision</p>
  </div>

  <div class="prompt-box">
    <h3>
      <span>System Prompt</span>
      <button class="copy-btn" onclick="copyPrompt()">Copy Prompt</button>
    </h3>
    <div class="prompt-text" id="promptText">You are an advanced document analysis AI. Your task is to read this tax invoice image line by line from top to bottom.

Extract ONLY the following 7 fields in exact order:
1. Dealership Name (from the header at the very top)
2. Document Type (Tax Invoice / GST Invoice label)
3. GST Invoice Number and Date
4. Customer Name (exactly as printed)
5. OEM Loyalty Discount or Welcome Bonus Discount amount
6. Customer Signature (Status: Present/Missing, and does it match the name?)
7. Dealership Stamp and Seal (Printed name, designation, reverse charge status)

OUTPUT FORMAT:
Return a strictly valid JSON array containing exactly 7 objects. 
Each object must have "field" and "value" keys.
Do not include markdown blocks, explanations, or extra text.
Example:
[
  {{"field": "Dealership Name", "value": "Example Motors Ltd"}},
  ...
]</div>
  </div>

  <button class="run-btn" id="runBtn" onclick="analyzeDocument()">
    Analyze Document via OpenAI Vision
  </button>

  <div class="status" id="status">Connecting to OpenAI GPT-4o Vision model...</div>

  <div class="results" id="results">
    <div class="section-title">Extraction Results & Cropped Context</div>
    <div id="cards"></div>
  </div>
</div>

<script>
{crops_str}

{pdf_str}

function copyPrompt() {{
  const text = document.getElementById('promptText').innerText;
  navigator.clipboard.writeText(text);
}}

async function analyzeDocument() {{
  const btn = document.getElementById('runBtn');
  const status = document.getElementById('status');
  const results = document.getElementById('results');

  btn.disabled = true;
  btn.textContent = 'Analyzing...';
  status.style.display = 'block';
  status.textContent = 'Sending document to OpenAI GPT-4o vision api...';

  try {{
    const base64Data = PDF_B64.startsWith('data:') ? PDF_B64 : `data:image/jpeg;base64,${{PDF_B64}}`;
    
    const response = await fetch("https://api.openai.com/v1/chat/completions", {{
      method: "POST",
      headers: {{ 
        "Content-Type": "application/json",
        "Authorization": "Bearer YOUR_OPENAI_API_KEY_HERE"
      }},
      body: JSON.stringify({{
        model: "gpt-4o",
        messages: [{{
          role: "user",
          content: [
            {{
              type: "text",
              text: document.getElementById('promptText').innerText
            }},
            {{
              type: "image_url",
              image_url: {{
                url: base64Data
              }}
            }}
          ]
        }}],
        max_tokens: 1000,
        temperature: 0.1
      }})
    }});

    const data = await response.json();
    
    let raw = "";
    if (data.choices && data.choices.length > 0) {{
      raw = data.choices[0].message.content;
    }} else if (data.error) {{
      throw new Error(data.error.message || "OpenAI API Error");
    }}

    let parsed;
    try {{
      const clean = raw.replace(/```json|```/g, "").trim();
      parsed = JSON.parse(clean);
    }} catch(e) {{
      status.textContent = "Could not parse API response. Showing pre-analyzed results.";
      parsed = null;
    }}

    renderCards(parsed);
    status.style.display = 'none';
    results.style.display = 'block';

  }} catch(e) {{
    status.textContent = `API error (${{e.message}}) — showing pre-analyzed results.`;
    renderCards(null);
    results.style.display = 'block';
  }}

  btn.disabled = false;
  btn.textContent = 'Re-analyze Document ↗';
}}

function renderCards(apiResults) {{
  const container = document.getElementById('cards');
  container.innerHTML = '';

  CROPS.forEach((crop, i) => {{
    const apiVal = apiResults && apiResults[i] ? apiResults[i].value : null;

    const card = document.createElement('div');
    card.className = 'card';
    card.innerHTML = `
      <div class="card-header">
        <div class="card-num">${{i+1}}</div>
        <div class="card-label">${{crop.label}}</div>
      </div>
      <img class="card-img" src="data:image/jpeg;base64,${{crop.b64}}" alt="${{crop.label}}" />
      <div class="card-detail">
        <div class="detail-field">${{crop.field}}</div>
        <div class="detail-value">${{crop.value}}</div>
        ${{apiVal ? `<div class="ai-section"><span class="ai-label">OpenAI Vision</span><div class="ai-value">${{apiVal}}</div></div>` : ''}}
      </div>
    `;
    container.appendChild(card);
  }});
}}

window.onload = () => {{
  renderCards(null);
  document.getElementById('results').style.display = 'block';
}};
</script>
</body>
</html>
"""

with open(r'c:\Users\admin\Desktop\robbinmahindra\invoice_analyzer.html', 'w', encoding='utf-8') as f:
    f.write(new_content)

print("Update completed successfully.")
