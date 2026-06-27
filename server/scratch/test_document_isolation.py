import sys
import os
import time
import io

# Setup import path for project root and api
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))) # api folder
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))) # project root

from fastapi.testclient import TestClient
from server.main import app
from server.utils.neo4j_client import neo4j_client
from server.config import config

# Force MULTI_DOCUMENT_MODE to True for testing validation of coexisting document graphs
config.MULTI_DOCUMENT_MODE = True

client = TestClient(app)

def get_automata_pdf_bytes() -> bytes:
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    ml_pdf = os.path.join(project_root, "test_assets", "test_machine_learning.pdf")
    
    with open(ml_pdf, 'rb') as f:
        content = f.read()
    
    # Replace characters keeping exact length
    text_content = content.decode('latin-1')
    text_content = text_content.replace('Machine Learning', 'Automata Theory ')
    text_content = text_content.replace('machine learning', 'automata theory ')
    text_content = text_content.replace('Attention', 'Automaton')
    text_content = text_content.replace('attention', 'automaton')
    text_content = text_content.replace('Transformers', 'Computations')
    text_content = text_content.replace('transformers', 'computations')
    text_content = text_content.replace('Transformer', 'Computation')
    text_content = text_content.replace('transformer', 'computation')
    text_content = text_content.replace('Linear Algebra', 'Finite Automata')
    text_content = text_content.replace('Neural Networks', 'Regular Grammar')
    text_content = text_content.replace('neural networks', 'regular grammar')
    text_content = text_content.replace('Backpropagation', 'Regular Expr.  ')
    text_content = text_content.replace('Gradient Descent', 'NFA and DFA-desc')
    
    return text_content.encode('latin-1')

def get_ml_pdf_bytes() -> bytes:
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    ml_pdf = os.path.join(project_root, "test_assets", "test_machine_learning.pdf")
    with open(ml_pdf, 'rb') as f:
        return f.read()

def poll_status(doc_id: str):
    for _ in range(20):
        res = client.get(f"/documents/{doc_id}/status")
        assert res.status_code == 200
        data = res.json()
        if data.get("status") in ["done", "error"]:
            return data
        time.sleep(0.5)
    raise TimeoutError("Extraction pipeline timeout.")

def test_document_graph_isolation():
    # Clear mock databases initially to guarantee fresh run
    if neo4j_client.is_mock():
        neo4j_client.mock_nodes.clear()
        neo4j_client.mock_edges.clear()

    print("\n=== [1] Uploading Document A (Automata Theory) ===")
    pdf_a_bytes = get_automata_pdf_bytes()
    
    res = client.post(
        "/documents/upload",
        files={"file": ("automata.pdf", pdf_a_bytes, "application/pdf")}
    )
    assert res.status_code == 200
    doc_a = res.json()["id"]
    print(f"Document A uploaded. ID: {doc_a}")
    
    # Wait for completion
    status_a = poll_status(doc_a)
    assert status_a.get("status") == "done", f"Document A extraction failed: {status_a.get('error')}"
    
    # Fetch Graph A
    graph_a_res = client.get(f"/documents/{doc_a}/graph")
    assert graph_a_res.status_code == 200
    graph_a = graph_a_res.json()
    
    nodes_a = graph_a.get("nodes", [])
    edges_a = graph_a.get("edges", [])
    
    print(f"Document A Graph: Nodes={len(nodes_a)}, Edges={len(edges_a)}")
    
    # Assert nodes are Automata concepts
    node_names_a = {n["name"].lower() for n in nodes_a}
    print("Document A Concepts:", node_names_a)
    
    assert any("automata" in name or "dfa" in name or "nfa" in name for name in node_names_a), "Expected Automata concepts in Graph A"
    assert not any("transformer" in name or "attention" in name for name in node_names_a), "Did not expect Machine Learning concepts in Graph A"

    print("\n=== [2] Uploading Document B (Machine Learning) ===")
    pdf_b_bytes = get_ml_pdf_bytes()
    
    res = client.post(
        "/documents/upload",
        files={"file": ("ml.pdf", pdf_b_bytes, "application/pdf")}
    )
    assert res.status_code == 200
    doc_b = res.json()["id"]
    print(f"Document B uploaded. ID: {doc_b}")
    
    # Wait for completion
    status_b = poll_status(doc_b)
    assert status_b.get("status") == "done", f"Document B extraction failed: {status_b.get('error')}"
    
    # Fetch Graph B
    graph_b_res = client.get(f"/documents/{doc_b}/graph")
    assert graph_b_res.status_code == 200
    graph_b = graph_b_res.json()
    
    nodes_b = graph_b.get("nodes", [])
    edges_b = graph_b.get("edges", [])
    
    print(f"Document B Graph: Nodes={len(nodes_b)}, Edges={len(edges_b)}")
    
    # Assert nodes are ML concepts
    node_names_b = {n["name"].lower() for n in nodes_b}
    print("Document B Concepts:", node_names_b)
    
    assert any("transformer" in name or "attention" in name or "neural" in name for name in node_names_b), "Expected ML concepts in Graph B"
    assert not any("automata" in name or "dfa" in name or "nfa" in name for name in node_names_b), "Did not expect Automata concepts in Graph B"

    # Assert that Document A concepts do not display in Document B's graph
    intersection = node_names_a.intersection(node_names_b)
    print("Shared concepts between Document A and Document B:", intersection)
    assert len(intersection) == 0 or (len(intersection) == 1 and list(intersection)[0] == "unknown"), "Concepts leaked between documents!"

    # Verify query validation locks
    print("\n=== [3] Verifying Cross-Document API Query Validation Locks ===")
    
    # Find a node ID from Graph A and one from Graph B
    node_id_a = nodes_a[0]["id"]
    node_id_b = nodes_b[0]["id"]
    
    # A: GET /graph/node/{node_id_a}?document_id={doc_b} (Mismatch)
    print(f"Testing node details lookup with mismatched document_id...")
    res_details = client.get(f"/graph/node/{node_id_a}?document_id={doc_b}")
    assert res_details.status_code == 403, f"Expected 403 Forbidden, got {res_details.status_code}"
    print("  Node details check correctly rejected with 403.")
    
    # B: GET /graph/node/{node_id_a}?document_id={doc_a} (Valid)
    res_details_ok = client.get(f"/graph/node/{node_id_a}?document_id={doc_a}")
    assert res_details_ok.status_code == 200
    print(f"  Valid node details returned HTTP {res_details_ok.status_code}.")

    # C: GET /graph/expand?node_id={node_id_a}&document_id={doc_b} (Mismatch)
    print("Testing expand endpoint with mismatched document_id...")
    res_expand = client.get(f"/graph/expand?node_id={node_id_a}&depth=1&mode=basic&document_id={doc_b}")
    assert res_expand.status_code == 403, f"Expected 403 Forbidden, got {res_expand.status_code}"
    print("  Graph expansion correctly rejected with 403.")

    # D: GET /learning-path?target={node_id_a}&document_id={doc_b} (Mismatch)
    print("Testing learning-path generation with mismatched document_id...")
    res_path = client.get(f"/learning-path?target={node_id_a}&document_id={doc_b}")
    assert res_path.status_code == 403, f"Expected 403 Forbidden, got {res_path.status_code}"
    print("  Learning path generation correctly rejected with 403.")

    # E: GET /graph/path?from_id={node_id_a}&to_id={node_id_b}&document_id={doc_b} (Mismatch)
    print("Testing shortest path traversal with mismatched node ownership...")
    res_shortest = client.get(f"/graph/path?from_id={node_id_a}&to_id={node_id_b}&document_id={doc_b}")
    assert res_shortest.status_code == 403, f"Expected 403 Forbidden, got {res_shortest.status_code}"
    print("  Shortest path correctly rejected with 403.")

    print("\nALL DOCUMENT ISOLATION TESTS PASSED SUCCESSFULLY!")

if __name__ == "__main__":
    test_document_graph_isolation()
