import uuid
import datetime
import logging
import json
from typing import Optional
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from api.utils.neo4j_client import neo4j_client
from api.utils.llm_client import llm_client
from api.config import config

router = APIRouter()
logger = logging.getLogger("notes_router")

class NoteCreate(BaseModel):
    content: str

def run_concept_linking_for_note(note_id: str, content: str):
    # Fetch existing concepts
    query = "MATCH (c:Concept) RETURN c.id as id, c.name as name"
    concepts = neo4j_client.run_query(query)
    
    matched_ids = []
    new_concept = None
    
    content_lower = content.lower()
    
    # 1. Local scanning rule (Mock Mode)
    for c in concepts:
        c_name = c["name"].lower()
        if c_name in content_lower:
            matched_ids.append(c["id"])
            
    # Propose new concept if keywords match and no concepts cover it
    if "neural" in content_lower and not any("neural" in c["name"].lower() for c in concepts):
        new_concept = "Neural Networks"
    elif "transformer" in content_lower and not any("transformer" in c["name"].lower() for c in concepts):
        new_concept = "Transformers"

    # 2. Real LLM execution
    is_mock = not config.ANTHROPIC_API_KEY or "mock-api-key" in config.ANTHROPIC_API_KEY
    if not is_mock and llm_client._client:
        try:
            concept_list_str = ", ".join([f"{c['name']} (ID: {c['id']})" for c in concepts])
            prompt = (
                f"Given this note content: '{content}'\n"
                f"And this list of existing concepts: {concept_list_str}\n\n"
                f"Identify if this note references or describes any of the existing concepts. "
                f"Return the matched IDs. If it describes a key concept that is not in the list, "
                f"propose its name in 'new_concept' (keep it short like 'Self-attention').\n"
                f"Return ONLY valid JSON matching this schema:\n"
                f"{{\"matched_ids\": [\"id1\", \"id2\"], \"new_concept\": null | \"concept_name\"}}"
            )
            
            res = llm_client._client.messages.create(
                model=config.ANTHROPIC_MODEL,
                max_tokens=1000,
                temperature=0,
                messages=[{"role": "user", "content": prompt}]
            )
            content_res = res.content[0].text.strip()
            
            # Clean markdown formatting fences
            if content_res.startswith("```json"): content_res = content_res[7:]
            if content_res.startswith("```"): content_res = content_res[3:]
            if content_res.endswith("```"): content_res = content_res[:-3]
            
            data = json.loads(content_res.strip())
            matched_ids = data.get("matched_ids", [])
            new_concept = data.get("new_concept")
        except Exception as e:
            logger.error(f"Failed to use real LLM for concept linking: {e}")

    # Create links in Neo4j
    for cid in matched_ids:
        link_query = """
        MATCH (n:Note {id: $nid})
        MATCH (c:Concept {id: $cid})
        MERGE (n)-[:REFERENCES]->(c)
        """
        neo4j_client.run_query(link_query, {"nid": note_id, "cid": cid})
        
        # Link in mock database
        if neo4j_client.is_mock():
            neo4j_client.mock_edges.append({"from": note_id, "to": cid, "type": "REFERENCES"})
        
    if new_concept:
        new_id = str(uuid.uuid4())
        concept_query = """
        MATCH (n:Note {id: $nid})
        MERGE (c:Concept {name: $name})
        ON CREATE SET c.id = $cid, c.provisional = true, c.description = 'Provisional concept created from note.'
        MERGE (n)-[:REFERENCES]->(c)
        """
        neo4j_client.run_query(concept_query, {"nid": note_id, "name": new_concept, "cid": new_id})
        
        # Write to mock store
        if neo4j_client.is_mock():
            neo4j_client.mock_nodes[new_id] = {
                "id": new_id,
                "label": "Concept",
                "name": new_concept,
                "description": "Provisional concept created from note.",
                "difficulty_level": "Beginner",
                "provisional": True
            }
            neo4j_client.mock_edges.append({"from": note_id, "to": new_id, "type": "REFERENCES"})

@router.post("/notes")
def create_note(request: NoteCreate):
    nid = str(uuid.uuid4())
    created_at = datetime.datetime.now().isoformat()
    
    # Save Note node
    query = """
    MERGE (n:Note {id: $id})
    ON CREATE SET n.content = $content, n.created_at = $created_at
    RETURN n
    """
    neo4j_client.run_query(query, {
        "id": nid,
        "content": request.content,
        "created_at": created_at
    })
    
    # Mock data write
    if neo4j_client.is_mock():
        neo4j_client.mock_nodes[nid] = {
            "id": nid,
            "label": "Note",
            "content": request.content,
            "created_at": created_at
        }
        
    # Execute AI concept-linking
    run_concept_linking_for_note(nid, request.content)
    
    return {
        "id": nid,
        "content": request.content,
        "created_at": created_at
    }

@router.get("/notes")
def get_notes():
    if neo4j_client.is_mock():
        results = []
        for nid, node in neo4j_client.mock_nodes.items():
            if node.get("label") == "Note":
                # Gather referenced concept names
                linked_concepts = []
                for edge in neo4j_client.mock_edges:
                    if edge["from"] == nid and edge["type"] == "REFERENCES":
                        concept = neo4j_client.mock_nodes.get(edge["to"])
                        if concept:
                            linked_concepts.append(concept.get("name", "Unknown"))
                            
                results.append({
                    "id": node["id"],
                    "content": node["content"],
                    "created_at": node["created_at"],
                    "concepts": linked_concepts
                })
        return results

    query = """
    MATCH (n:Note)
    OPTIONAL MATCH (n)-[:REFERENCES]->(c:Concept)
    RETURN n.id as id, n.content as content, n.created_at as created_at, collect(c.name) as concepts
    """
    res = neo4j_client.run_query(query)
    return [
        {
            "id": r["id"],
            "content": r["content"],
            "created_at": r["created_at"],
            "concepts": r["concepts"]
        }
        for r in res
    ]

@router.get("/notes/search")
def search_notes(q: str = Query(...)):
    if neo4j_client.is_mock():
        # Scans mock notes and matches on text or linked concept names
        results = []
        q_low = q.lower()
        
        all_notes = get_notes()
        for note in all_notes:
            content_match = q_low in note["content"].lower()
            concept_match = any(q_low in c.lower() for c in note["concepts"])
            
            if content_match or concept_match:
                results.append(note)
        return results

    query = """
    MATCH (n:Note)
    OPTIONAL MATCH (n)-[:REFERENCES]->(c:Concept)
    WITH n, c
    WHERE n.content CONTAINS $q OR c.name CONTAINS $q
    RETURN n.id as id, n.content as content, n.created_at as created_at, collect(c.name) as concepts
    """
    res = neo4j_client.run_query(query, {"q": q})
    return [
        {
            "id": r["id"],
            "content": r["content"],
            "created_at": r["created_at"],
            "concepts": r["concepts"]
        }
        for r in res
    ]
