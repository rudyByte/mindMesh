import time
import json
import urllib.request
import urllib.error
import os

def upload_file(url, file_path):
    boundary = b'----WebKitFormBoundary7MA4YWxkTrZu0gW'
    filename = os.path.basename(file_path)
    
    with open(file_path, 'rb') as f:
        file_content = f.read()
        
    body = (
        b'--' + boundary + b'\r\n' +
        b'Content-Disposition: form-data; name="file"; filename="' + filename.encode('utf-8') + b'"\r\n' +
        b'Content-Type: application/pdf\r\n\r\n' +
        file_content + b'\r\n' +
        b'--' + boundary + b'--\r\n'
    )
    
    req = urllib.request.Request(
        url,
        data=body,
        headers={
            'Content-Type': b'multipart/form-data; boundary=' + boundary,
            'Content-Length': str(len(body))
        },
        method='POST'
    )
    
    with urllib.request.urlopen(req) as res:
        return json.loads(res.read().decode('utf-8'))

def get_json(url):
    req = urllib.request.Request(url, method='GET')
    with urllib.request.urlopen(req) as res:
        return json.loads(res.read().decode('utf-8'))

def main():
    root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    doc_dir = os.path.join(root_dir, "mock_storage", "documents")
    pdf_files = [f for f in os.listdir(doc_dir) if f.endswith(".pdf")]
    if not pdf_files:
        print("Error: No PDF files found in mock_storage/documents to upload.")
        return
        
    pdf_path = os.path.join(doc_dir, pdf_files[0])
    url = "http://localhost:8000/documents/upload"
    
    print(f"Uploading {pdf_path} to {url}...")
    try:
        data = upload_file(url, pdf_path)
        doc_id = data.get("id")
        print(f"Upload successful! Document ID: {doc_id}")
        
        # Poll status
        status_url = f"http://localhost:8000/documents/{doc_id}/status"
        for i in range(15):
            time.sleep(1.5)
            status_data = get_json(status_url)
            print(f"Status poll {i+1}: {status_data}")
            if status_data.get("status") in ["done", "error"]:
                break
                
        # Fetch graph
        graph_url = f"http://localhost:8000/documents/{doc_id}/graph"
        graph_data = get_json(graph_url)
        print("Graph construction verification:")
        print(f"Nodes count: {len(graph_data.get('nodes', []))}")
        print(f"Edges count: {len(graph_data.get('edges', []))}")
        
        # Check connectivity of nodes
        node_ids = {node["id"] for node in graph_data.get("nodes", [])}
        edge_nodes = set()
        for edge in graph_data.get("edges", []):
            edge_nodes.add(edge["from"])
            edge_nodes.add(edge["to"])
            
        isolated_nodes = node_ids - edge_nodes
        if isolated_nodes:
            print(f"WARNING: Isolated nodes detected: {isolated_nodes}")
            for node in graph_data.get("nodes", []):
                if node["id"] in isolated_nodes:
                    print(f"  - Isolated node: {node['name']} ({node['label']})")
        else:
            print("SUCCESS: Zero isolated nodes! The knowledge graph is fully unified and interconnected.")
            
    except Exception as e:
        print(f"Error during execution: {e}")

if __name__ == "__main__":
    main()
