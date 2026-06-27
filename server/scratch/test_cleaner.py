import sys
import os
import io
import re
import unicodedata
from collections import Counter
from pypdf import PdfReader

# Set Python path to find the 'api' directory
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8')

from server.utils.text_cleaner import clean_pdf_text_from_bytes

def main():
    root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    doc_dir = os.path.join(root_dir, "mock_storage", "documents")
    pdf_files = [f for f in os.listdir(doc_dir) if f.endswith(".pdf")]
    
    if not pdf_files:
        print("No PDF files found.")
        return
        
    for target_pdf in pdf_files:
        pdf_path = os.path.join(doc_dir, target_pdf)
        print(f"\n\n==================== Reading and cleaning: {target_pdf} ====================")
        
        with open(pdf_path, "rb") as f:
            file_bytes = f.read()
            
        reader = PdfReader(io.BytesIO(file_bytes))
        raw_text = ""
        for i, page in enumerate(reader.pages):
            raw_text += f"\n\n--- Page {i+1} ---\n\n" + (page.extract_text() or "")
            
        print("\n--- RAW TEXT PREVIEW (First 300 chars) ---")
        print(repr(raw_text[:300]))
        
        cleaned_text, _ = clean_pdf_text_from_bytes(file_bytes)
        
        print("\n--- CLEANED TEXT PREVIEW (First 500 chars) ---")
        print(cleaned_text[:500])

if __name__ == "__main__":
    main()
