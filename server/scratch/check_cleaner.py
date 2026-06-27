import sys
import os

# Set Python path to find the 'api' directory
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from server.utils.text_cleaner import clean_pdf_text_from_bytes
from pypdf import PdfReader

def main():
    root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    doc_path = os.path.join(root_dir, "mock_storage", "documents", "3d2f879c-6270-48be-a5ad-71606b8c88ff_messy doc.pdf")
    
    print(f"Reading: {doc_path}")
    with open(doc_path, "rb") as f:
        file_bytes = f.read()
        
    reader = PdfReader(doc_path)
    raw_text = ""
    for i, page in enumerate(reader.pages):
        raw_text += f"\n\n--- Page {i+1} ---\n\n" + (page.extract_text() or "")
        
    print("\n--- RAW TEXT PREVIEW ---")
    print(raw_text)
    
    cleaned_text, _ = clean_pdf_text_from_bytes(file_bytes)
    
    print("\n--- CLEANED TEXT PREVIEW ---")
    print(cleaned_text)

if __name__ == "__main__":
    main()
