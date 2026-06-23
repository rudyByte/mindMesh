from fastapi import APIRouter, HTTPException, Query
from api.utils.neo4j_client import neo4j_client

router = APIRouter()

@router.get("/graph/node/{id}")
def get_node_details(id: str, document_id: str = Query(..., description="Document ID to validate ownership")):
    if neo4j_client.is_mock():
        res = neo4j_client.run_query("MATCH (N {ID: $id})", {"id": id, "document_id": document_id})
        if res:
            record = res[0]
            return {
                "id": record.get("id"),
                "label": record.get("label"),
                "name": record.get("name") or record.get("title") or "Unknown",
                "description": record.get("description") or "",
                "difficulty_level": record.get("difficulty_level") or "Beginner",
                "year": record.get("year"),
                "doi": record.get("doi")
            }
        # Differentiate 403 vs 404 in mock mode
        if id in neo4j_client.mock_nodes:
            raise HTTPException(status_code=403, detail="Access denied. Node does not belong to the specified document.")
        raise HTTPException(status_code=404, detail="Node not found.")

    # Real Neo4j Mode: query must verify that the Document contains the node
    query = """
    MATCH (d:Document {id: $doc_id})-[:CONTAINS]->(n {id: $id}) 
    RETURN labels(n)[0] as label, n.id as id, n.name as name, n.description as description, 
           n.difficulty_level as difficulty_level, n.title as title, n.year as year, n.doi as doi
    """
    res = neo4j_client.run_query(query, {"id": id, "doc_id": document_id})
    if not res:
        # Check if the node exists globally to throw 403 instead of 404
        exists_query = "MATCH (n {id: $id}) RETURN n.id"
        exists_res = neo4j_client.run_query(exists_query, {"id": id})
        if exists_res:
            raise HTTPException(status_code=403, detail="Access denied. Node does not belong to the specified document.")
        else:
            raise HTTPException(status_code=404, detail="Node not found.")
            
    record = res[0]
    name = record.get("name") or record.get("title") or "Unknown"
    return {
        "id": record.get("id"),
        "label": record.get("label"),
        "name": name,
        "description": record.get("description") or "",
        "difficulty_level": record.get("difficulty_level") or "Beginner",
        "year": record.get("year"),
        "doi": record.get("doi")
    }

@router.get("/graph/expand")
def expand_graph(
    node_id: str = Query(..., description="ID of node to expand"),
    depth: int = Query(1, ge=1, le=3, description="Depth of path expansion"),
    mode: str = Query("basic", description="Expansion mode: basic (prerequisites) or advanced (related/extends)"),
    document_id: str = Query(..., description="Document ID to validate ownership and restrict traversal")
):
    if neo4j_client.is_mock():
        res = neo4j_client.run_query("MATCH path", {"id": node_id, "depth": depth, "mode": mode, "document_id": document_id})
        if res:
            # If target node exists but document_id filtering returned empty nodes because of mismatch
            nodes = res[0].get("nodes", [])
            if not nodes:
                # If target node exists globally in mock
                if node_id in neo4j_client.mock_nodes:
                    raise HTTPException(status_code=403, detail="Access denied. Target node does not belong to the specified document.")
                else:
                    raise HTTPException(status_code=404, detail="Target node not found.")
            return res[0]
        return {"nodes": [], "edges": []}

    # 1. Verify target node belongs to document
    target_query = """
    MATCH (d:Document {id: $doc_id})-[:CONTAINS]->(target {id: $id})
    RETURN labels(target)[0] as label, target.id as id, target.name as name, target.description as description, target.difficulty_level as difficulty_level
    """
    target_res = neo4j_client.run_query(target_query, {"id": node_id, "doc_id": document_id})
    if not target_res:
        # Check if the node exists globally
        exists_query = "MATCH (n {id: $id}) RETURN n.id"
        exists_res = neo4j_client.run_query(exists_query, {"id": node_id})
        if exists_res:
            raise HTTPException(status_code=403, detail="Access denied. Target node does not belong to the specified document.")
        else:
            raise HTTPException(status_code=404, detail="Target node not found.")

    nodes_dict = {}
    edges_list = []
    
    t = target_res[0]
    nodes_dict[t["id"]] = {
        "id": t["id"],
        "label": t["label"],
        "name": t["name"] or "Unknown",
        "description": t.get("description", ""),
        "difficulty_level": t.get("difficulty_level", "Beginner")
    }
    
    # 2. Query path expansion, enforcing that all traversed nodes are contained in the document
    if mode == "basic":
        cypher = """
        MATCH (d:Document {id: $doc_id})
        MATCH p=(target {id: $id})<-[:PREREQUISITE_OF*1..$depth]-(n)
        WHERE ALL(x IN nodes(p) WHERE (d)-[:CONTAINS]->(x))
        RETURN p
        """
    else:
        cypher = """
        MATCH (d:Document {id: $doc_id})
        MATCH p=(target {id: $id})-[:EXTENDS|RELATED_TO*1..$depth]-(n)
        WHERE ALL(x IN nodes(p) WHERE (d)-[:CONTAINS]->(x))
        RETURN p
        """
        
    path_res = neo4j_client.run_query(cypher, {"id": node_id, "depth": depth, "doc_id": document_id})
    
    for record in path_res:
        path = record.get("p")
        if not path:
            continue
        
        for node in path.nodes:
            nid = node.get("id")
            if nid not in nodes_dict:
                label = list(node.labels)[0] if node.labels else "Concept"
                nodes_dict[nid] = {
                    "id": nid,
                    "label": label,
                    "name": node.get("name") or node.get("title") or "Unknown",
                    "description": node.get("description", ""),
                    "difficulty_level": node.get("difficulty_level", "Beginner")
                }
                
        for rel in path.relationships:
            start_id = rel.start_node.get("id")
            end_id = rel.end_node.get("id")
            
            edge_exists = any(e["from"] == start_id and e["to"] == end_id and e["type"] == rel.type for e in edges_list)
            if not edge_exists:
                edges_list.append({
                    "from": start_id,
                    "to": end_id,
                    "type": rel.type
                })
                
    nodes = list(nodes_dict.values())
    if len(nodes) > 150:
        nodes = nodes[:150]
        active_ids = {n["id"] for n in nodes}
        edges_list = [e for e in edges_list if e["from"] in active_ids and e["to"] in active_ids]
        
    return {"nodes": nodes, "edges": edges_list}

@router.get("/graph/path")
def get_shortest_path(
    from_id: str, 
    to_id: str,
    document_id: str = Query(..., description="Document ID to validate ownership and restrict path")
):
    if neo4j_client.is_mock():
        res = neo4j_client.run_query("MATCH path", {"from_id": from_id, "to_id": to_id, "document_id": document_id})
        # If either node doesn't belong to the document, run_query will filter them out or return empty
        # Validate that both from_id and to_id exist in mock and belong to this document
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

        if from_id not in doc_node_ids or to_id not in doc_node_ids:
            raise HTTPException(status_code=403, detail="Access denied. Nodes do not belong to the specified document.")

        if res:
            return res[0]
        return {"nodes": [], "edges": []}
        
    # Real Neo4j Mode
    query = """
    MATCH (d:Document {id: $doc_id})
    MATCH (start {id: $from_id}), (end {id: $to_id})
    WHERE (d)-[:CONTAINS]->(start) AND (d)-[:CONTAINS]->(end)
    MATCH p = shortestPath((start)-[*..10]-(end))
    WHERE ALL(x IN nodes(p) WHERE (d)-[:CONTAINS]->(x))
    RETURN p
    """
    res = neo4j_client.run_query(query, {"from_id": from_id, "to_id": to_id, "doc_id": document_id})
    
    # Validation if no path found but nodes exist to throw 403 vs 404
    if not res:
        # Check if they exist in document
        check_query = """
        MATCH (d:Document {id: $doc_id})
        MATCH (start {id: $from_id}), (end {id: $to_id})
        RETURN (d)-[:CONTAINS]->(start) as start_ok, (d)-[:CONTAINS]->(end) as end_ok
        """
        check_res = neo4j_client.run_query(check_query, {"from_id": from_id, "to_id": to_id, "doc_id": document_id})
        if not check_res or not check_res[0]["start_ok"] or not check_res[0]["end_ok"]:
            raise HTTPException(status_code=403, detail="Access denied. Nodes do not belong to the specified document.")

    nodes_dict = {}
    edges_list = []
    
    if res and res[0].get("p"):
        path = res[0]["p"]
        for node in path.nodes:
            nid = node.get("id")
            label = list(node.labels)[0] if node.labels else "Concept"
            nodes_dict[nid] = {
                "id": nid,
                "label": label,
                "name": node.get("name") or node.get("title") or "Unknown",
                "description": node.get("description", ""),
                "difficulty_level": node.get("difficulty_level", "Beginner")
            }
        for rel in path.relationships:
            edges_list.append({
                "from": rel.start_node.get("id"),
                "to": rel.end_node.get("id"),
                "type": rel.type
            })
            
    return {"nodes": list(nodes_dict.values()), "edges": edges_list}
