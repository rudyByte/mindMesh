import sys
import os
from pypdf import PdfReader

def main():
    root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    pdf_path = os.path.join(root_dir, "mock_storage", "documents", "e1d93ab9-4d63-4605-96c3-42f512542926_test.pdf")
    
    print(f"Reading PDF from: {pdf_path}")
    if not os.path.exists(pdf_path):
        print("File does not exist.")
        return
        
    reader = PdfReader(pdf_path)
    print(f"Number of pages: {len(reader.pages)}")
    text = ""
    for i, page in enumerate(reader.pages[:5]):  # print first 5 pages info
        page_text = page.extract_text() or ""
        print(f"\n--- Page {i+1} (Length: {len(page_text)}) ---")
        print(page_text[:1000])

if __name__ == "__main__":
    sys.stdout.reconfigure(encoding='utf-8')
    main()
