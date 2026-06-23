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
def get_learning_path(target: str = Query(..., description="ID of target concept")):
    # 1. Verify target concept exists
    target_node = None
    if neo4j_client.is_mock():
        if target in neo4j_client.mock_nodes:
            target_node = neo4j_client.mock_nodes[target]
    else:
        res = neo4j_client.run_query("""
            MATCH (c:Concept {id: $target_id})
            RETURN c.id as id, c.name as name, c.description as description, c.difficulty_level as difficulty_level
        """, {"target_id": target})
        if res:
            target_node = res[0]

    if not target_node:
        raise HTTPException(status_code=404, detail="Target concept not found.")

    # 2. Get path nodes list
    path_nodes = []
    
    if neo4j_client.is_mock():
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
        # Try path starting from a root
        query_root = """
        MATCH path = (start:Concept)-[:PREREQUISITE_OF*1..5]->(target:Concept {id: $target_id})
        WHERE NOT (start)<-[:PREREQUISITE_OF]-()
        RETURN [n in nodes(path) | {
            id: n.id,
            label: labels(n)[0],
            name: coalesce(n.name, n.title, "Unknown"),
            description: coalesce(n.description, ""),
            difficulty_level: coalesce(n.difficulty_level, "Beginner")
        }] as nodes_list
        ORDER BY length(path) DESC LIMIT 1
        """
        res = neo4j_client.run_query(query_root, {"target_id": target})
        
        # Fallback to any path ending at target if no root path
        if not res:
            query_any = """
            MATCH path = (start:Concept)-[:PREREQUISITE_OF*1..5]->(target:Concept {id: $target_id})
            RETURN [n in nodes(path) | {
                id: n.id,
                label: labels(n)[0],
                name: coalesce(n.name, n.title, "Unknown"),
                description: coalesce(n.description, ""),
                difficulty_level: coalesce(n.difficulty_level, "Beginner")
            }] as nodes_list
            ORDER BY length(path) DESC LIMIT 1
            """
            res = neo4j_client.run_query(query_any, {"target_id": target})
            
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
