from typing import Optional
from fastapi import APIRouter, HTTPException, Query
from server.utils.neo4j_client import neo4j_client
from server.utils.llm_client import llm_client

router = APIRouter()
_prerequisites_cache = {}

def get_primary_label(labels_list) -> str:
    if not labels_list:
        return "Concept"
    if isinstance(labels_list, str):
        labels_list = [labels_list]
    for lbl in ["Topic", "Subtopic", "Technology", "Framework", "Application", "Concept", "Paper", "Author", "Institution", "Keyword", "Method", "Dataset"]:
        if lbl in labels_list:
            return lbl
    return "Concept"

@router.get("/graph/node/{id}")
def get_node_details(
    id: str, 
    document_id: Optional[str] = Query(None, description="Document ID to validate ownership"),
    session_id: Optional[str] = Query(None, description="Session ID to validate ownership")
):
    # If UI sends a fallback ID from the roadmap like 'roadmap-Electric Charge'
    concept_name = id.replace("roadmap-", "")
    
    record = None
    if neo4j_client.is_mock():
        res = neo4j_client.run_query("MATCH (N {ID: $id})", {"id": id, "document_id": document_id, "session_id": session_id})
        if res:
            record = res[0]
            record["labels"] = [record.get("label")]
        else:
            if id in neo4j_client.mock_nodes:
                if session_id:
                    raise HTTPException(status_code=403, detail="Access denied.")
                else:
                    raise HTTPException(status_code=403, detail="Access denied.")
    else:
        if session_id:
            query = """
            MATCH (n {id: $id, session_id: $session_id}) 
            RETURN labels(n) as labels, n.id as id, n.name as name, n.description as description, 
                   n.difficulty_level as difficulty_level, n.title as title, n.year as year, n.doi as doi
            """
            res = neo4j_client.run_query(query, {"id": id, "session_id": session_id})
        else:
            query = """
            MATCH (d:Document {id: $doc_id})-[:CONTAINS]->(n {id: $id}) 
            RETURN labels(n) as labels, n.id as id, n.name as name, n.description as description, 
                   n.difficulty_level as difficulty_level, n.title as title, n.year as year, n.doi as doi
            """
            res = neo4j_client.run_query(query, {"id": id, "doc_id": document_id})
            
        if not res:
            exists_query = "MATCH (n {id: $id}) RETURN n.id"
            exists_res = neo4j_client.run_query(exists_query, {"id": id})
            if exists_res:
                raise HTTPException(status_code=403, detail="Access denied.")
        else:
            record = res[0]
            
    # Base response object
    node_data = {
        "id": id,
        "label": "Concept",
        "name": concept_name,
        "description": "",
        "difficulty_level": "Beginner"
    }
    
    if record:
        node_data["label"] = get_primary_label(record.get("labels", ["Concept"]))
        node_data["name"] = record.get("name") or record.get("title") or concept_name
        node_data["description"] = record.get("description") or ""
        node_data["difficulty_level"] = record.get("difficulty_level") or "Beginner"
        if record.get("year"): node_data["year"] = record.get("year")
        if record.get("doi"): node_data["doi"] = record.get("doi")
        concept_name = node_data["name"]
        
    # Dynamically synthesize exhaustive breakdown from LLM
    llm_details = llm_client.generate_concept_details(concept_name)
    
    # Merge LLM details (definition, formula, unit, origin_or_context)
    node_data.update(llm_details)
    
    # Return merged object, completely bypassing the HTTP 404 Error!
    return node_data
@router.get("/graph/prerequisites/{node_id}")
def get_node_prerequisites(
    node_id: str,
    document_id: Optional[str] = Query(None, description="Document ID to validate ownership"),
    session_id: Optional[str] = Query(None, description="Session ID to validate ownership")
):
    if node_id in _prerequisites_cache:
        return {"prerequisites": _prerequisites_cache[node_id]}
        
    prereqs = []
    target_name = "Unknown"
    
    if neo4j_client.is_mock():
        if node_id.startswith('llm-req-'):
            target_name = node_id.replace('llm-req-', '').replace('-', ' ').title()
        else:
            target_node = neo4j_client.mock_nodes.get(node_id)
            if not target_node:
                raise HTTPException(status_code=404, detail="Target node not found.")
            target_name = target_node.get("name") or target_node.get("title") or "Unknown"
            
        # 1. Look for explicit PREREQUISITE edges (req -> target)
        for edge in neo4j_client.mock_edges:
            if edge["to"] == node_id and edge["type"] in ["PREREQUISITE_OF", "DEPENDS_ON"]:
                req_node = neo4j_client.mock_nodes.get(edge["from"])
                if req_node and req_node not in prereqs:
                    prereqs.append(req_node)
    else:
        # Real Neo4j Mode
        if node_id.startswith('llm-req-'):
            target_name = node_id.replace('llm-req-', '').replace('-', ' ').title()
        else:
            query_explicit = """
            MATCH (req)-[:PREREQUISITE_OF|DEPENDS_ON]->(target {id: $node_id})
            RETURN target.name as target_name, req.id as id, labels(req)[0] as label, coalesce(req.name, req.title, "Unknown") as name, coalesce(req.description, "") as description
            """
            res = neo4j_client.run_query(query_explicit, {"node_id": node_id})
            if res:
                target_name = res[0]["target_name"]
                prereqs = [{"id": r["id"], "label": r["label"], "name": r["name"], "description": r["description"]} for r in res]
            else:
                res_target = neo4j_client.run_query("MATCH (target {id: $node_id}) RETURN target.name as name", {"node_id": node_id})
                if res_target:
                    target_name = res_target[0]["name"]
                
    # Use LLM to generate more prereqs
    if target_name and target_name != "Unknown":
        llm_prereqs_raw = llm_client.generate_prerequisites(target_name)
        
        # Merge LLM prereqs (append if not duplicate by name)
        existing_names = {p["name"].lower() for p in prereqs if "name" in p}
        
        for lp in llm_prereqs_raw:
            if lp.get("name") and lp["name"].lower() not in existing_names:
                node_id = f"llm-req-{lp['name'].replace(' ', '-').lower()}"
                
                if not neo4j_client.is_mock():
                    match_query = "MATCH (n) WHERE toLower(coalesce(n.name, n.title)) = toLower($name) RETURN n.id as id LIMIT 1"
                    match_res = neo4j_client.run_query(match_query, {"name": lp["name"]})
                    if match_res:
                        node_id = match_res[0]["id"]
                else:
                    for mock_node in neo4j_client.mock_nodes.values():
                        if (mock_node.get("name") or mock_node.get("title") or "").lower() == lp["name"].lower():
                            node_id = mock_node["id"]
                            break
                            
                prereqs.append({
                    "id": node_id,
                    "label": "Concept",
                    "name": lp["name"],
                    "description": lp.get("description", "")
                })
                existing_names.add(lp["name"].lower())
                
    _prerequisites_cache[node_id] = prereqs
    return {"prerequisites": prereqs}

@router.get("/graph/expand")
def expand_graph(
    node_id: str = Query(..., description="ID of node to expand"),
    depth: int = Query(1, ge=1, le=3, description="Depth of path expansion"),
    mode: str = Query("basic", description="Expansion mode: basic (prerequisites) or advanced (related/extends)"),
    document_id: Optional[str] = Query(None, description="Document ID to validate ownership and restrict traversal"),
    session_id: Optional[str] = Query(None, description="Session ID to validate ownership and restrict traversal")
):
    if neo4j_client.is_mock():
        res = neo4j_client.run_query("MATCH path", {"id": node_id, "depth": depth, "mode": mode, "document_id": document_id, "session_id": session_id})
        if res:
            # If target node exists but document_id/session_id filtering returned empty nodes because of mismatch
            nodes = res[0].get("nodes", [])
            if not nodes:
                # If target node exists globally in mock
                if node_id in neo4j_client.mock_nodes:
                    if session_id:
                        raise HTTPException(status_code=403, detail="Access denied. Target node does not belong to the specified session.")
                    else:
                        raise HTTPException(status_code=403, detail="Access denied. Target node does not belong to the specified document.")
                else:
                    raise HTTPException(status_code=404, detail="Target node not found.")
            return res[0]
        return {"nodes": [], "edges": []}

    # 1. Verify target node belongs to document/session
    if session_id:
        target_query = """
        MATCH (target {id: $id, session_id: $session_id})
        RETURN labels(target)[0] as label, target.id as id, target.name as name, target.description as description, target.difficulty_level as difficulty_level
        """
        target_res = neo4j_client.run_query(target_query, {"id": node_id, "session_id": session_id})
    else:
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
            if session_id:
                raise HTTPException(status_code=403, detail="Access denied. Target node does not belong to the specified session.")
            else:
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
    
    # 2. Query path expansion, enforcing that all traversed nodes are contained in the document/session
    if session_id:
        if mode == "basic":
            cypher = """
            MATCH p=(target {id: $id, session_id: $session_id})<-[:PREREQUISITE_OF|DEPENDS_ON*1..$depth]-(n)
            WHERE ALL(x IN nodes(p) WHERE x.session_id = $session_id) AND ALL(r IN relationships(p) WHERE r.session_id = $session_id)
            RETURN p
            """
        else:
            cypher = """
            MATCH p=(target {id: $id, session_id: $session_id})-[:EXTENDS|RELATED_TO|USES|CITES|CONTAINS|PREREQUISITE_OF|USES_METHOD|DEPENDS_ON|AUTHORED_BY|MENTIONS|HAS_KEYWORD*1..$depth]-(n)
            WHERE ALL(x IN nodes(p) WHERE x.session_id = $session_id) AND ALL(r IN relationships(p) WHERE r.session_id = $session_id)
            RETURN p
            """
    else:
        if mode == "basic":
            cypher = """
            MATCH (d:Document {id: $doc_id})
            MATCH p=(target {id: $id})<-[:PREREQUISITE_OF|DEPENDS_ON*1..$depth]-(n)
            WHERE ALL(x IN nodes(p) WHERE (d)-[:CONTAINS]->(x)) AND ALL(r IN relationships(p) WHERE r.doc_id = $doc_id)
            RETURN p
            """
        else:
            cypher = """
            MATCH (d:Document {id: $doc_id})
            MATCH p=(target {id: $id})-[:EXTENDS|RELATED_TO|USES|CITES|CONTAINS|PREREQUISITE_OF|USES_METHOD|DEPENDS_ON|AUTHORED_BY|MENTIONS|HAS_KEYWORD*1..$depth]-(n)
            WHERE ALL(x IN nodes(p) WHERE (d)-[:CONTAINS]->(x)) AND ALL(r IN relationships(p) WHERE r.doc_id = $doc_id)
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
                label = get_primary_label(list(node.labels)) if node.labels else "Concept"
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
    document_id: Optional[str] = Query(None, description="Document ID to validate ownership and restrict path"),
    session_id: Optional[str] = Query(None, description="Session ID to validate ownership and restrict path")
):
    if neo4j_client.is_mock():
        res = neo4j_client.run_query("MATCH path", {"from_id": from_id, "to_id": to_id, "document_id": document_id, "session_id": session_id})
        # If either node doesn't belong to the document/session, validate in mock
        doc_node_ids = set()
        if session_id:
            for nid, n in neo4j_client.mock_nodes.items():
                if n.get("session_id") == session_id:
                    doc_node_ids.add(nid)
        elif document_id == "doc-1":
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
            if session_id:
                raise HTTPException(status_code=403, detail="Access denied. Nodes do not belong to the specified session.")
            else:
                raise HTTPException(status_code=403, detail="Access denied. Nodes do not belong to the specified document.")

        if res:
            return res[0]
        return {"nodes": [], "edges": []}
        
    # Real Neo4j Mode
    if session_id:
        query = """
        MATCH (start {id: $from_id, session_id: $session_id}), (end {id: $to_id, session_id: $session_id})
        MATCH p = shortestPath((start)-[*..10]-(end))
        WHERE ALL(x IN nodes(p) WHERE x.session_id = $session_id) AND ALL(r IN relationships(p) WHERE r.session_id = $session_id)
        RETURN p
        """
        res = neo4j_client.run_query(query, {"from_id": from_id, "to_id": to_id, "session_id": session_id})
    else:
        query = """
        MATCH (d:Document {id: $doc_id})
        MATCH (start {id: $from_id}), (end {id: $to_id})
        WHERE (d)-[:CONTAINS]->(start) AND (d)-[:CONTAINS]->(end)
        MATCH p = shortestPath((start)-[*..10]-(end))
        WHERE ALL(x IN nodes(p) WHERE (d)-[:CONTAINS]->(x)) AND ALL(r IN relationships(p) WHERE r.doc_id = $doc_id)
        RETURN p
        """
        res = neo4j_client.run_query(query, {"from_id": from_id, "to_id": to_id, "doc_id": document_id})
    
    # Validation if no path found but nodes exist to throw 403 vs 404
    if not res:
        # Check if they exist in document/session
        if session_id:
            check_query = """
            MATCH (start {id: $from_id}), (end {id: $to_id})
            RETURN start.session_id = $session_id as start_ok, end.session_id = $session_id as end_ok
            """
            check_res = neo4j_client.run_query(check_query, {"from_id": from_id, "to_id": to_id, "session_id": session_id})
        else:
            check_query = """
            MATCH (d:Document {id: $doc_id})
            MATCH (start {id: $from_id}), (end {id: $to_id})
            RETURN (d)-[:CONTAINS]->(start) as start_ok, (d)-[:CONTAINS]->(end) as end_ok
            """
            check_res = neo4j_client.run_query(check_query, {"from_id": from_id, "to_id": to_id, "doc_id": document_id})
            
        if not check_res or not check_res[0]["start_ok"] or not check_res[0]["end_ok"]:
            if session_id:
                raise HTTPException(status_code=403, detail="Access denied. Nodes do not belong to the specified session.")
            else:
                raise HTTPException(status_code=403, detail="Access denied. Nodes do not belong to the specified document.")

    nodes_dict = {}
    edges_list = []
    
    if res and res[0].get("p"):
        path = res[0]["p"]
        for node in path.nodes:
            nid = node.get("id")
            label = get_primary_label(list(node.labels)) if node.labels else "Concept"
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

@router.get("/learning-roadmap/{node_id}")
def get_learning_roadmap(
    node_id: str,
    document_id: Optional[str] = Query(None, description="Document ID"),
    session_id: Optional[str] = Query(None, description="Session ID")
):
    selected_node = {"id": node_id, "name": "Unknown"}
    
    if neo4j_client.is_mock():
        node = neo4j_client.mock_nodes.get(node_id)
        if node:
            selected_node = {
                "id": node_id,
                "label": node.get("label", "Concept"),
                "name": node.get("name") or node.get("title") or "Unknown",
                "description": node.get("description", "")
            }
    else:
        # First find the selected node to get its name for the LLM
        query = "MATCH (n {id: $node_id}) RETURN n.id as id, labels(n)[0] as label, coalesce(n.name, n.title, 'Unknown') as name, coalesce(n.description, '') as description"
        res = neo4j_client.run_query(query, {"node_id": node_id})
        if res:
            selected_node = res[0]
            
    # STEP 1: Bypass DB Relationships for Path Generation
    # Use LLM to dynamically generate a clean, rigorous, step-by-step prerequisite roadmap
    roadmap = llm_client.generate_dynamic_roadmap(selected_node["name"])

    return {
        "selectedNode": selected_node,
        "roadmap": roadmap
    }
