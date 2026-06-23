import sys
import os
import asyncio
import io

# Setup import path for project root
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

async def test_pipeline_on_pdf(pdf_path: str, expect_success: bool):
    print(f"\n--- Testing PDF: {os.path.basename(pdf_path)} (Expect Success: {expect_success}) ---")
    
    from fastapi import UploadFile, BackgroundTasks
    from api.routers.documents import upload_document, get_document_status, get_document_graph
    
    with open(pdf_path, 'rb') as f:
        file_bytes = f.read()
        
    class MockBackgroundTasks(BackgroundTasks):
        def __init__(self):
            super().__init__()
            self.tasks = []
        def add_task(self, func, *args, **kwargs):
            self.tasks.append((func, args, kwargs))
            
    bg_tasks = MockBackgroundTasks()
    
    mock_file = UploadFile(
        file=io.BytesIO(file_bytes),
        filename=os.path.basename(pdf_path)
    )
    
    res = await upload_document(background_tasks=bg_tasks, file=mock_file)
    doc_id = res.id
    print(f"  Uploaded. Doc ID: {doc_id}")
    
    if bg_tasks.tasks:
        func, args, kwargs = bg_tasks.tasks[0]
        try:
            func(*args, **kwargs)
            print("  Pipeline function completed.")
        except Exception as e:
            print(f"  Pipeline function raised exception: {e}")
            
    status_res = get_document_status(doc_id)
    print(f"  Final Document Status: {status_res}")
    
    if expect_success:
        assert status_res.status == 'done', f"Expected status 'done', got '{status_res.status}'"
        assert status_res.error is None, f"Expected no error, got '{status_res.error}'"
        # retrieve graph
        graph_res = get_document_graph(doc_id)
        print(f"  Graph count: Nodes={len(graph_res.get('nodes', []))}, Edges={len(graph_res.get('edges', []))}")
        assert len(graph_res.get('nodes', [])) > 0, "Expected nodes in graph"
    else:
        assert status_res.status == 'error', f"Expected status 'error', got '{status_res.status}'"
        assert status_res.error is not None, "Expected an error message"
        assert "exceeds 80% limit" in status_res.error, f"Expected error to mention 80% limit, got: {status_res.error}"
        print(f"  Successfully blocked noisy PDF! Error: {status_res.error}")

async def main():
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    ml_pdf = os.path.join(project_root, "test_assets", "test_machine_learning.pdf")
    noisy_pdf = os.path.join(project_root, "test_assets", "test_noisy.pdf")
    
    if not os.path.exists(ml_pdf):
        print(f"Error: {ml_pdf} not found. Please create assets first.")
        return
    if not os.path.exists(noisy_pdf):
        print(f"Error: {noisy_pdf} not found. Please create assets first.")
        return
        
    await test_pipeline_on_pdf(ml_pdf, expect_success=True)
    await test_pipeline_on_pdf(noisy_pdf, expect_success=False)
    
    print("\n=== MULTIPLE PDF PIPELINE VALIDATION TEST PASSED! ===")

if __name__ == "__main__":
    asyncio.run(main())
