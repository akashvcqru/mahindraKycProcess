import os
import glob
from pypdf import PdfReader

def inspect_pdfs():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    documents_dir = os.path.join(script_dir, "..", "documents") # relative to scratch folder
    documents_dir = os.path.abspath(documents_dir)
    
    print(f"Searching for PDFs in: {documents_dir}")
    pdf_files = glob.glob(os.path.join(documents_dir, "**", "*.pdf"), recursive=True)
    
    if not pdf_files:
        print("No PDF files found in documents/ directory.")
        return
        
    for pdf_path in pdf_files:
        rel_path = os.path.relpath(pdf_path, documents_dir)
        print(f"\n==========================================")
        print(f"FILE: {rel_path}")
        print(f"==========================================")
        
        try:
            reader = PdfReader(pdf_path)
            num_pages = len(reader.pages)
            print(f"Pages: {num_pages}")
            
            # Extract and print text from each page
            full_text = []
            for i, page in enumerate(reader.pages):
                text = page.extract_text()
                if text:
                    full_text.append(text)
                    print(f"--- PAGE {i+1} Text ---")
                    print(text[:1000]) # print first 1000 chars of each page
                else:
                    print(f"--- PAGE {i+1} contains NO SELECTABLE TEXT ---")
                    
            entire_content = "\n".join(full_text).strip()
            if not entire_content:
                print("WARNING: This PDF has NO selectable text (it is likely a scanned image/photo).")
            else:
                print(f"Total extracted character count: {len(entire_content)}")
                
        except Exception as e:
            print(f"Error reading PDF: {e}")

if __name__ == "__main__":
    inspect_pdfs()
