from fastapi import APIRouter, HTTPException, Query
from utils.neo4j_client import neo4j_client
from utils.llm_client import llm_client

router = APIRouter()

def find_mock_longest_path(target_id: str, visited: set) -> list:
    if target_id in visited:
        return []
    visited.add(target_id)
    longest_subpath = []
    for edge in neo4j_client.mock_edges:
        if edge["to"] == target_id and edge["type"] == "PREREQUISITE_OF":
            subpath = find_mock_longest_path(edge["from"], visited.copy())
            if len(subpath) > len(longest_subpath):
                longest_subpath = subpath
    return longest_subpath + [target_id]

@router.get("/learning-path")
def get_learning_path(
    target: str = Query(..., description="ID of target concept"),
    document_id: str = Query(..., description="Document ID to validate ownership and restrict path")
):
    # 1. Verify target concept exists and belongs to the document
    target_node = None
    if neo4j_client.is_mock():
        if target in neo4j_client.mock_nodes:
            target_node = neo4j_client.mock_nodes[target]
            # Validate ownership in mock mode
            if document_id != "doc-1":
                has_contains = any(
                    e["from"] == document_id and e["to"] == target and e["type"] == "CONTAINS"
                    for e in neo4j_client.mock_edges
                )
                if not has_contains and target_node.get("doc_id") != document_id:
                    raise HTTPException(status_code=403, detail="Access denied. Target concept does not belong to the specified document.")
    else:
        # Verify that document contains target
        res = neo4j_client.run_query("""
            MATCH (d:Document {id: $doc_id})-[:CONTAINS]->(c:Concept {id: $target_id})
            RETURN c.id as id, c.name as name, c.description as description, c.difficulty_level as difficulty_level
        """, {"target_id": target, "doc_id": document_id})
        if res:
            target_node = res[0]
        else:
            # Check if it exists at all to throw correct error
            exists_res = neo4j_client.run_query("MATCH (c {id: $target_id}) RETURN c.id", {"target_id": target})
            if exists_res:
                raise HTTPException(status_code=403, detail="Access denied. Target concept does not belong to the specified document.")

    if not target_node:
        raise HTTPException(status_code=404, detail="Target concept not found.")

    # 2. Get path nodes list
    path_nodes = []
    
    if neo4j_client.is_mock():
        # Restrict mock longest path search to nodes belonging to this document ID
        doc_node_ids = set()
        if document_id == "doc-1":
            for nid, n in neo4j_client.mock_nodes.items():
                if n.get("label") != "Document":
                    doc_node_ids.add(nid)
        else:
            for edge in neo4j_client.mock_edges:
                if edge["from"] == document_id and edge["type"] == "CONTAINS":
                    doc_node_ids.add(edge["to"])
            for nid, n in neo4j_client.mock_nodes.items():
                if n.get("doc_id") == document_id:
                    doc_node_ids.add(nid)

        def find_mock_longest_path(curr_id: str, visited: set) -> list:
            if curr_id in visited or curr_id not in doc_node_ids:
                return []
            visited.add(curr_id)
            longest_subpath = []
            for edge in neo4j_client.mock_edges:
                if edge["to"] == curr_id and edge["type"] == "PREREQUISITE_OF" and edge["from"] in doc_node_ids:
                    subpath = find_mock_longest_path(edge["from"], visited.copy())
                    if len(subpath) > len(longest_subpath):
                        longest_subpath = subpath
            return longest_subpath + [curr_id]

        path_ids = find_mock_longest_path(target, set())
        for pid in path_ids:
            node = neo4j_client.mock_nodes.get(pid)
            if node:
                path_nodes.append({
                    "id": node["id"],
                    "label": node.get("label", "Concept"),
                    "name": node.get("name") or node.get("title") or "Unknown",
                    "description": node.get("description", ""),
                    "difficulty_level": node.get("difficulty_level", "Beginner")
                })
    else:
        # Try path starting from a root, enforcing all path nodes are contained in the document
        query_root = """
        MATCH (d:Document {id: $doc_id})
        MATCH path = (start:Concept)-[:PREREQUISITE_OF*1..5]->(target:Concept {id: $target_id})
        WHERE ALL(x IN nodes(path) WHERE (d)-[:CONTAINS]->(x))
        AND NOT (start)<-[:PREREQUISITE_OF]-()
        RETURN [n in nodes(path) | {
            id: n.id,
            label: labels(n)[0],
            name: coalesce(n.name, n.title, "Unknown"),
            description: coalesce(n.description, ""),
            difficulty_level: coalesce(n.difficulty_level, "Beginner")
        }] as nodes_list
        ORDER BY length(path) DESC LIMIT 1
        """
        res = neo4j_client.run_query(query_root, {"target_id": target, "doc_id": document_id})
        
        # Fallback to any path ending at target if no root path
        if not res:
            query_any = """
            MATCH (d:Document {id: $doc_id})
            MATCH path = (start:Concept)-[:PREREQUISITE_OF*1..5]->(target:Concept {id: $target_id})
            WHERE ALL(x IN nodes(path) WHERE (d)-[:CONTAINS]->(x))
            RETURN [n in nodes(path) | {
                id: n.id,
                label: labels(n)[0],
                name: coalesce(n.name, n.title, "Unknown"),
                description: coalesce(n.description, ""),
                difficulty_level: coalesce(n.difficulty_level, "Beginner")
            }] as nodes_list
            ORDER BY length(path) DESC LIMIT 1
            """
            res = neo4j_client.run_query(query_any, {"target_id": target, "doc_id": document_id})
            
        if res and res[0].get("nodes_list"):
            path_nodes = res[0]["nodes_list"]
        else:
            # No prerequisites found at all, return just the target node
            path_nodes = [{
                "id": target_node.get("id"),
                "label": "Concept",
                "name": target_node.get("name") or target_node.get("title") or "Unknown",
                "description": target_node.get("description") or "",
                "difficulty_level": target_node.get("difficulty_level") or "Beginner"
            }]

    # 3. Create edges list
    edges = []
    for i in range(len(path_nodes) - 1):
        edges.append({
            "from": path_nodes[i]["id"],
            "to": path_nodes[i+1]["id"],
            "type": "PREREQUISITE_OF"
        })

    # 4. Generate AI narration
    concept_names = [n["name"] for n in path_nodes]
    narration = llm_client.narrate_learning_path(concept_names)

    return {
        "nodes": path_nodes,
        "edges": edges,
        "narration": narration
    }
