import sys
import os
import uuid
import pytest
from fastapi.testclient import TestClient

# Setup import path for project root and api
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))) # api folder
sys.path.insert(1, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))) # project root

from main import app
from utils.neo4j_client import neo4j_client
from routers.documents import run_extraction_pipeline, extraction_status_cache

client = TestClient(app)

def test_label_interchangeability_and_duplicate_prevention():
    """
    Test that concept-like labels (Concept, Topic, Keyword, Author) are merged interchangeably 
    without creating duplicate nodes for the same name and session.
    """
    if neo4j_client.is_mock():
        neo4j_client.mock_nodes.clear()
        neo4j_client.mock_edges.clear()

    session_id = f"test-session-{uuid.uuid4()}"
    doc_id = f"test-doc-{uuid.uuid4()}"

    # 1. Create a Topic node
    res1 = client.get(f"/sessions/{session_id}/graph")
    assert res1.status_code == 200

    # Simulate ingestion merging "Self-Attention" as a Topic
    if neo4j_client.is_mock():
        neo4j_client.run_query(
            "MERGE (n:Topic {name: $name, session_id: $session_id})",
            {"name": "Self-Attention", "session_id": session_id, "id": "node-1", "description": "A topic desc", "doc_id": doc_id}
        )
    else:
        neo4j_client.run_query(
            "MERGE (n:Concept {name: $name, session_id: $session_id}) SET n:Topic SET n.id = $id, n.description = $description, n.doc_id = $doc_id",
            {"name": "Self-Attention", "session_id": session_id, "id": "node-1", "description": "A topic desc", "doc_id": doc_id}
        )

    # 2. Simulate merging the same concept name but as a Keyword. It should reuse the existing node!
    if neo4j_client.is_mock():
        res = neo4j_client.run_query(
            "MERGE (n:Keyword {name: $name, session_id: $session_id})",
            {"name": "Self-Attention", "session_id": session_id, "id": "node-2", "description": "A keyword desc", "doc_id": doc_id}
        )
        resolved_id = res[0]["node_id"]
        assert resolved_id == "node-1", "Should have resolved to existing node-1 instead of creating duplicates!"
    else:
        res = neo4j_client.run_query(
            "MERGE (n:Concept {name: $name, session_id: $session_id}) SET n:Keyword RETURN n.id as node_id",
            {"name": "Self-Attention", "session_id": session_id}
        )
        # Verify only 1 node with name "Self-Attention" exists in the database
        count_res = neo4j_client.run_query(
            "MATCH (n {session_id: $session_id}) WHERE n.name = $name RETURN count(n) as cnt",
            {"session_id": session_id, "name": "Self-Attention"}
        )
        assert count_res[0]["cnt"] == 1, "Duplicate nodes created for different concept labels!"

    print("\n[PASS] Label interchangeability and duplicate prevention verification passed.")

def test_copilot_session_and_document_isolation():
    """
    Test that /copilot/context and /copilot/chat return 403 Forbidden when requested
    with a node belonging to a different session or document.
    """
    if neo4j_client.is_mock():
        neo4j_client.mock_nodes.clear()
        neo4j_client.mock_edges.clear()

    session_a = "session-a"
    session_b = "session-b"
    node_a = "node-in-session-a"
    node_b = "node-in-session-b"

    # Seed nodes
    if neo4j_client.is_mock():
        neo4j_client.mock_nodes[node_a] = {"id": node_a, "label": "Concept", "name": "Concept A", "session_id": session_a}
        neo4j_client.mock_nodes[node_b] = {"id": node_b, "label": "Concept", "name": "Concept B", "session_id": session_b}
    else:
        neo4j_client.run_query("MATCH (n) DETACH DELETE n")
        neo4j_client.run_query("CREATE (n:Concept {id: $id, name: 'Concept A', session_id: $session_id})", {"id": node_a, "session_id": session_a})
        neo4j_client.run_query("CREATE (n:Concept {id: $id, name: 'Concept B', session_id: $session_id})", {"id": node_b, "session_id": session_b})

    # Test /copilot/context: querying node_a with session_b context -> expect 403
    res_context = client.post(
        "/copilot/context",
        json={"node_id": node_a, "session_id": session_b}
    )
    assert res_context.status_code == 403, f"Expected 403, got {res_context.status_code}"

    # Test /copilot/chat: querying node_a with session_b context -> expect 403
    res_chat = client.post(
        "/copilot/chat",
        json={"message": "Explain this", "node_id": node_a, "session_id": session_b}
    )
    assert res_chat.status_code == 403, f"Expected 403, got {res_chat.status_code}"

    print("[PASS] Copilot session context isolation verification passed.")

def test_citations_and_highlights_session_isolation():
    """
    Test that Citations and Highlights cannot be created linking to Papers or Documents 
    from another session (returns 403).
    """
    session_a = "session-a"
    session_b = "session-b"
    doc_b = "doc-in-session-b"
    paper_b = "paper-in-session-b"

    # Seed Document and Paper in Session B
    if neo4j_client.is_mock():
        neo4j_client.mock_nodes[doc_b] = {"id": doc_b, "label": "Document", "title": "Doc B.pdf", "session_id": session_b}
        neo4j_client.mock_nodes[paper_b] = {"id": paper_b, "label": "Paper", "title": "Paper B", "session_id": session_b}
    else:
        neo4j_client.run_query("MATCH (n) DETACH DELETE n")
        neo4j_client.run_query("CREATE (d:Document {id: $id, title: 'Doc B.pdf', session_id: $session_id})", {"id": doc_b, "session_id": session_b})
        neo4j_client.run_query("CREATE (p:Paper {id: $id, title: 'Paper B', session_id: $session_id})", {"id": paper_b, "session_id": session_b})

    # 1. POST /highlights under session_a referencing doc_b -> expect 403
    res_highlight = client.post(
        f"/highlights?session_id={session_a}",
        json={"text": "A key sentence", "page": 1, "source_document_id": doc_b}
    )
    assert res_highlight.status_code == 403

    # 2. POST /citations under session_a referencing paper_b -> expect 403
    res_citation = client.post(
        f"/citations?session_id={session_a}",
        json={"paper_id": paper_b, "style": "APA"}
    )
    assert res_citation.status_code == 403

    print("[PASS] Citations and highlights session isolation verification passed.")

def test_ingestion_failure_cleanup():
    """
    Test that if ingestion throws an exception during processing, all nodes and relationships
    created under that doc_id are automatically cleaned up to prevent graph contamination.
    """
    if neo4j_client.is_mock():
        neo4j_client.mock_nodes.clear()
        neo4j_client.mock_edges.clear()

    session_id = "test-session"
    doc_id = "test-doc-failing"

    # Seed Document node
    if neo4j_client.is_mock():
        neo4j_client.mock_nodes[doc_id] = {"id": doc_id, "label": "Document", "title": "test_noisy.pdf", "session_id": session_id}
    else:
        neo4j_client.run_query("MATCH (n) DETACH DELETE n")
        neo4j_client.run_query("CREATE (d:Document {id: $id, session_id: $session_id})", {"id": doc_id, "session_id": session_id})

    # Trigger extraction pipeline but force failure by passing corrupted bytes (triggering value error)
    try:
        run_extraction_pipeline(doc_id, b"not-a-valid-pdf-bytes", "test_noisy.pdf", session_id)
    except Exception:
        pass

    # Verify that the status cache is in 'error' state
    status = extraction_status_cache.get(doc_id)
    assert status is not None
    assert status["status"] == "error"

    # Verify that no nodes or edges tagged with doc_id exist in the database/mock store
    if neo4j_client.is_mock():
        doc_nodes = [n for n in neo4j_client.mock_nodes.values() if n.get("doc_id") == doc_id]
        doc_edges = [e for e in neo4j_client.mock_edges if e.get("doc_id") == doc_id]
        assert len(doc_nodes) == 0, "Failed ingestion run nodes were not cleaned up!"
        assert len(doc_edges) == 0, "Failed ingestion run relationships were not cleaned up!"
    else:
        res = neo4j_client.run_query("MATCH (n) WHERE n.doc_id = $doc_id RETURN count(n) as cnt", {"doc_id": doc_id})
        assert res[0]["cnt"] == 0, "Failing ingestion run left contaminated nodes in the Neo4j database!"

    print("[PASS] Ingestion failure cleanup verification passed.")

def test_replace_document_workflow():
    """
    Test that uploading a document with a replace_doc_id deletes the previous document,
    completely purges its associated nodes/edges, and creates the new document structure.
    """
    if neo4j_client.is_mock():
        neo4j_client.mock_nodes.clear()
        neo4j_client.mock_edges.clear()

    session_id = "test-replace-session"
    doc_old = "doc-old-id"
    node_old = "node-old-id"

    # Seed old document and concept
    if neo4j_client.is_mock():
        neo4j_client.mock_nodes[doc_old] = {
            "id": doc_old,
            "label": "Document",
            "title": "OldTextbook.pdf",
            "session_id": session_id,
            "storage_url": "file:///uploads/OldTextbook.pdf"
        }
        neo4j_client.mock_nodes[node_old] = {
            "id": node_old,
            "label": "Concept",
            "name": "Old Concept",
            "doc_id": doc_old,
            "session_id": session_id
        }
        neo4j_client.mock_edges.append({
            "from": doc_old,
            "to": node_old,
            "type": "CONTAINS",
            "doc_id": doc_old,
            "session_id": session_id
        })
    else:
        neo4j_client.run_query("MATCH (n) DETACH DELETE n")
        neo4j_client.run_query("CREATE (d:Document {id: $id, title: 'OldTextbook.pdf', session_id: $session_id, storage_url: 'file:///uploads/OldTextbook.pdf'})", {"id": doc_old, "session_id": session_id})
        neo4j_client.run_query("CREATE (c:Concept {id: $id, name: 'Old Concept', doc_id: $doc_id, session_id: $session_id})", {"id": node_old, "doc_id": doc_old, "session_id": session_id})
        neo4j_client.run_query("MATCH (d:Document {id: $doc_id}), (c:Concept {id: $c_id}) MERGE (d)-[:CONTAINS]->(c)", {"doc_id": doc_old, "c_id": node_old})

    # Call POST /documents/upload with replace_doc_id
    import io
    file_data = {"file": ("new_doc.pdf", io.BytesIO(b"dummy pdf bytes"), "application/pdf")}
    res = client.post(
        f"/documents/upload?session_id={session_id}&replace_doc_id={doc_old}",
        files=file_data
    )
    assert res.status_code == 200
    new_doc_id = res.json()["id"]

    # Verify that the old document and old concept are completely purged from database/mock
    if neo4j_client.is_mock():
        assert doc_old not in neo4j_client.mock_nodes
        assert node_old not in neo4j_client.mock_nodes
        assert len([e for e in neo4j_client.mock_edges if e.get("doc_id") == doc_old]) == 0
    else:
        old_doc_res = neo4j_client.run_query("MATCH (d:Document {id: $id}) RETURN d", {"id": doc_old})
        old_nodes_res = neo4j_client.run_query("MATCH (n) WHERE n.doc_id = $doc_id RETURN count(n) as cnt", {"doc_id": doc_old})
        assert len(old_doc_res) == 0
        assert old_nodes_res[0]["cnt"] == 0

    print("[PASS] Replace document workflow verification passed.")

if __name__ == "__main__":
    test_label_interchangeability_and_duplicate_prevention()
    test_copilot_session_and_document_isolation()
    test_citations_and_highlights_session_isolation()
    test_ingestion_failure_cleanup()
    test_replace_document_workflow()
    print("\nALL ARCHITECTURE AUDIT REGRESSION TESTS PASSED SUCCESSFULLY!")

