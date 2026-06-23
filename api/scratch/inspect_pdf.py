import sys
import os
from pypdf import PdfReader

def main():
    root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    doc_dir = os.path.join(root_dir, "mock_storage", "documents")
    pdf_files = [f for f in os.listdir(doc_dir) if f.endswith(".pdf")]
    if not pdf_files:
        print("Error: No PDF files found.")
        return
    pdf_path = os.path.join(doc_dir, pdf_files[0])
    
    print(f"Inspecting: {pdf_path}")
    reader = PdfReader(pdf_path)
    
    for page_idx in [2, 3, 4, 8]:  # pages 3, 4, 5, 9 (0-indexed: 2, 3, 4, 8)
        if page_idx >= len(reader.pages):
            continue
        page = reader.pages[page_idx]
        print(f"\n--- Page {page_idx + 1} ---")
        print("Images:", len(page.images))
        
        # Try extracting text with different layout orientations
        text_plain = page.extract_text() or ""
        print(f"Plain Extraction Length: {len(text_plain)}")
        
        # Let's check objects
        try:
            print("Resources keys:", list(page.resources.keys()) if page.resources else "None")
        except Exception as e:
            print("Failed to read resources:", e)

if __name__ == "__main__":
    main()
