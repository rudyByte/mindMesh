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
    
    artifact_dir = r"C:\Users\HARASIDDHI\.gemini\antigravity-ide\brain\900e92da-6048-4a6a-87a2-4f5b7e8615c7"
    os.makedirs(artifact_dir, exist_ok=True)
    
    print(f"Extracting images from: {pdf_path}")
    reader = PdfReader(pdf_path)
    
    for idx in [2, 3, 4, 8]:  # pages 3, 4, 5, 9
        if idx >= len(reader.pages):
            continue
        page = reader.pages[idx]
        print(f"\nProcessing Page {idx + 1}")
        
        images = page.images
        print(f"Number of images on page: {len(images)}")
        for img_idx, image_file in enumerate(images):
            img_name = f"page_{idx + 1}_img_{img_idx + 1}.png"
            img_path = os.path.join(artifact_dir, img_name)
            
            with open(img_path, "wb") as fp:
                fp.write(image_file.data)
            print(f"Saved image to: {img_path}")

if __name__ == "__main__":
    main()
