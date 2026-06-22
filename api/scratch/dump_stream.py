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
    
    reader = PdfReader(pdf_path)
    
    for idx in [2, 3, 4, 8]: # pages 3, 4, 5, 9
        if idx >= len(reader.pages):
            continue
        page = reader.pages[idx]
        print(f"\n--- Raw Contents Page {idx + 1} ---")
        contents = page.get_contents()
        if contents:
            # Print a snippet of the raw stream to see if there is text in TJ or Tj operators
            data = contents.get_data()
            print(f"Data length: {len(data)} bytes")
            # print first 500 bytes and search for Tj/TJ
            print("Preview:")
            print(data[:500])
            if b"Tj" in data or b"TJ" in data:
                print("Found Tj/TJ text operators in raw data!")
            else:
                print("No Tj/TJ text operators found in raw data.")
        else:
            print("No contents stream.")

if __name__ == "__main__":
    main()
