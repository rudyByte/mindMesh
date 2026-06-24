import sys
import os
from pypdf import PdfReader

def main():
    root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    assets_dir = os.path.join(root_dir, "test_assets")
    
    for filename in ["test_noisy.pdf", "test_machine_learning.pdf"]:
        pdf_path = os.path.join(assets_dir, filename)
        if not os.path.exists(pdf_path):
            print(f"File {filename} not found.")
            continue
            
        print(f"\n==================== {filename} ====================")
        reader = PdfReader(pdf_path)
        print(f"Total Pages: {len(reader.pages)}")
        for i, page in enumerate(reader.pages):
            text = page.extract_text() or ""
            print(f"--- Page {i+1} (Length: {len(text)}) ---")
            print(repr(text))

if __name__ == "__main__":
    main()
