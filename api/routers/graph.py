from fastapi import APIRouter, HTTPException, Query
from utils.neo4j_client import neo4j_client

router = APIRouter()

@router.get("/graph/node/{id}")
def get_node_details(id: str):
    # Fetch details for any node matching the ID
    query = """
    MATCH (n {id: $id}) 
    RETURN labels(n)[0] as label, n.id as id, n.name as name, n.description as description, 
           n.difficulty_level as difficulty_level, n.title as title, n.year as year, n.doi as doi
    """
    res = neo4j_client.run_query(query, {"id": id})
    if res:
        # In mock mode, the query will directly match
        record = res[0]
        # Consolidate display name (e.g. Paper title vs Concept name)
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
        
    # Check mock store directly if query didn't return
    if neo4j_client.is_mock() and id in neo4j_client.mock_nodes:
        n = neo4j_client.mock_nodes[id]
        return {
            "id": n.get("id"),
            "label": n.get("label"),
            "name": n.get("name") or n.get("title") or "Unknown",
            "description": n.get("description") or "",
            "difficulty_level": n.get("difficulty_level") or "Beginner",
            "year": n.get("year"),
            "doi": n.get("doi")
        }
        
    raise HTTPException(status_code=404, detail="Node not found.")

@router.get("/graph/expand")
def expand_graph(
    node_id: str = Query(..., description="ID of node to expand"),
    depth: int = Query(1, ge=1, le=3, description="Depth of path expansion"),
    mode: str = Query("basic", description="Expansion mode: basic (prerequisites) or advanced (related/extends)")
):
    if neo4j_client.is_mock():
        res = neo4j_client.run_query("MATCH path", {"id": node_id, "depth": depth, "mode": mode})
        if res:
            return res[0]
        return {"nodes": [], "edges": []}

    # 1. Fetch target node to ensure it is returned even if isolated
    target_query = """
    MATCH (n {id: $id}) 
    RETURN labels(n)[0] as label, n.id as id, n.name as name, n.description as description, n.difficulty_level as difficulty_level
    """
    target_res = neo4j_client.run_query(target_query, {"id": node_id})
    
    nodes_dict = {}
    edges_list = []
    
    if target_res:
        t = target_res[0]
        nodes_dict[t["id"]] = {
            "id": t["id"],
            "label": t["label"],
            "name": t["name"] or "Unknown",
            "description": t.get("description", ""),
            "difficulty_level": t.get("difficulty_level", "Beginner")
        }
        
    # 2. Query path expansion based on basic/advanced mode
    if mode == "basic":
        # Prerequisites (incoming links)
        cypher = """
        MATCH p=(target {id: $id})<-[:PREREQUISITE_OF*1..$depth]-(n)
        RETURN p
        """
    else:
        # Related to / Extends (outgoing or bidirection links)
        cypher = """
        MATCH p=(target {id: $id})-[:EXTENDS|RELATED_TO*1..$depth]-(n)
        RETURN p
        """
        
    path_res = neo4j_client.run_query(cypher, {"id": node_id, "depth": depth})
    
    for record in path_res:
        path = record.get("p")
        if not path:
            continue
        
        # Real Neo4j Path parsing
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
            
            # Avoid duplicate edges
            edge_exists = any(e["from"] == start_id and e["to"] == end_id and e["type"] == rel.type for e in edges_list)
            if not edge_exists:
                edges_list.append({
                    "from": start_id,
                    "to": end_id,
                    "type": rel.type
                })
                
    # Safeguard for limit (cap at 150 nodes to avoid crashing frontend)
    nodes = list(nodes_dict.values())
    if len(nodes) > 150:
        nodes = nodes[:150]
        # Filter edges to only include nodes present
        active_ids = {n["id"] for n in nodes}
        edges_list = [e for e in edges_list if e["from"] in active_ids and e["to"] in active_ids]
        
    return {"nodes": nodes, "edges": edges_list}

@router.get("/graph/path")
def get_shortest_path(from_id: str, to_id: str):
    if neo4j_client.is_mock():
        # Mock path return
        if from_id in neo4j_client.mock_nodes and to_id in neo4j_client.mock_nodes:
            return {
                "nodes": [neo4j_client.mock_nodes[from_id], neo4j_client.mock_nodes[to_id]],
                "edges": [{"from": from_id, "to": to_id, "type": "RELATED_TO"}]
            }
        return {"nodes": [], "edges": []}
        
    query = """
    MATCH (start {id: $from_id}), (end {id: $to_id})
    MATCH p = shortestPath((start)-[*..10]-(end))
    RETURN p
    """
    res = neo4j_client.run_query(query, {"from_id": from_id, "to_id": to_id})
    
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
