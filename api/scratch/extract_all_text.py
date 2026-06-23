import sys
import os
from pypdf import PdfReader

def main():
    root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    doc_dir = os.path.join(root_dir, "mock_storage", "documents")
    pdf_files = [f for f in os.listdir(doc_dir) if f.endswith(".pdf")]
    if not pdf_files:
        print("Error: No PDF files found in mock_storage/documents.")
        return
    pdf_path = os.path.join(doc_dir, pdf_files[0])
    output_path = os.path.join(root_dir, "api", "scratch", "extracted_paper_text.txt")
    
    if not os.path.exists(pdf_path):
        print(f"Error: {pdf_path} does not exist.")
        return
        
    reader = PdfReader(pdf_path)
    text = ""
    for i, page in enumerate(reader.pages):
        page_text = page.extract_text() or ""
        text += f"\n\n=== PAGE {i+1} ===\n\n{page_text}"
        
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(text)
        
    print(f"Extracted all text from {len(reader.pages)} pages to {output_path}")

if __name__ == "__main__":
    main()
