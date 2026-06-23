import uuid
import datetime
import logging
import json
from typing import Optional
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from utils.neo4j_client import neo4j_client
from utils.llm_client import llm_client
from config import config

router = APIRouter()
logger = logging.getLogger("highlights_router")

class HighlightCreate(BaseModel):
    text: str
    page: int
    source_document_id: str

def run_concept_linking_for_highlight(highlight_id: str, text: str, doc_id: str):
    # Fetch existing concepts for this document only
    query = "MATCH (c:Concept {doc_id: $doc_id}) RETURN c.id as id, c.name as name"
    concepts = neo4j_client.run_query(query, {"doc_id": doc_id})
    
    matched_ids = []
    new_concept = None
    
    text_lower = text.lower()
    
    # 1. Local scanning rule (Mock Mode)
    for c in concepts:
        c_name = c["name"].lower()
        if c_name in text_lower:
            matched_ids.append(c["id"])
            
    # Propose new concept if keywords match and no concepts cover it
    if "attention" in text_lower and not any("attention" in c["name"].lower() for c in concepts):
        new_concept = "Self-attention"
    elif "gradient" in text_lower and not any("gradient" in c["name"].lower() for c in concepts):
        new_concept = "Gradient Descent"

    # 2. Real LLM execution
    is_mock = not config.ANTHROPIC_API_KEY or "mock-api-key" in config.ANTHROPIC_API_KEY
    if not is_mock and llm_client._client:
        try:
            concept_list_str = ", ".join([f"{c['name']} (ID: {c['id']})" for c in concepts])
            prompt = (
                f"Given this highlight text extracted from a PDF: '{text}'\n"
                f"And this list of existing concepts: {concept_list_str}\n\n"
                f"Identify if this text clearly references or describes any of the existing concepts. "
                f"Return the matched IDs. If it describes a key concept that is not in the list, "
                f"propose its name in 'new_concept' (keep it short like 'Self-attention').\n"
                f"Return ONLY valid JSON matching this schema:\n"
                f"{{\n"
                f"  \"matched_ids\": [\n"
                f"    \"id1\"\n"
                f"  ],\n"
                f"  \"new_concept\": null\n"
                f"}}\n"
            )
            
            res = llm_client._client.messages.create(
                model=config.ANTHROPIC_MODEL,
                max_tokens=1000,
                temperature=0,
                messages=[{"role": "user", "content": prompt}]
            )
            content = res.content[0].text.strip()
            
            # Clean markdown formatting fences
            if content.startswith("```json"): content = content[7:]
            if content.startswith("```"): content = content[3:]
            if content.endswith("```"): content = content[:-3]
            
            data = json.loads(content.strip())
            matched_ids = data.get("matched_ids", [])
            new_concept = data.get("new_concept")
        except Exception as e:
            logger.error(f"Failed to use real LLM for concept linking: {e}")

    # Create links in Neo4j
    for cid in matched_ids:
        link_query = """
        MATCH (h:Highlight {id: $hid})
        MATCH (c:Concept {id: $cid})
        MERGE (h)-[:RELATES_TO]->(c)
        """
        neo4j_client.run_query(link_query, {"hid": highlight_id, "cid": cid})
        
        # Link in mock database
        if neo4j_client.is_mock():
            neo4j_client.mock_edges.append({"from": highlight_id, "to": cid, "type": "RELATES_TO"})
        
    if new_concept:
        new_id = str(uuid.uuid4())
        concept_query = """
        MATCH (h:Highlight {id: $hid})
        MERGE (c:Concept {name: $name, doc_id: $doc_id})
        ON CREATE SET c.id = $cid, c.provisional = true, c.description = 'Provisional concept created from highlight.'
        MERGE (h)-[:RELATES_TO]->(c)
        """
        neo4j_client.run_query(concept_query, {"hid": highlight_id, "name": new_concept, "cid": new_id, "doc_id": doc_id})
        
        # Write to mock store
        if neo4j_client.is_mock():
            neo4j_client.mock_nodes[new_id] = {
                "id": new_id,
                "label": "Concept",
                "name": new_concept,
                "description": "Provisional concept created from highlight.",
                "difficulty_level": "Beginner",
                "provisional": True,
                "doc_id": doc_id
            }
            neo4j_client.mock_edges.append({"from": highlight_id, "to": new_id, "type": "RELATES_TO"})

@router.post("/highlights")
def create_highlight(request: HighlightCreate):
    hid = str(uuid.uuid4())
    created_at = datetime.datetime.now().isoformat()
    
    # Save Highlight node
    query = """
    MERGE (h:Highlight {id: $id})
    ON CREATE SET h.text = $text, h.page = $page, h.source_type = 'pdf', h.created_at = $created_at
    RETURN h
    """
    neo4j_client.run_query(query, {
        "id": hid,
        "text": request.text,
        "page": request.page,
        "created_at": created_at
    })
    
    # Link to Document
    doc_link_query = """
    MATCH (h:Highlight {id: $hid})
    MATCH (d:Document {id: $doc_id})
    MERGE (h)-[:EXTRACTED_FROM]->(d)
    """
    neo4j_client.run_query(doc_link_query, {"hid": hid, "doc_id": request.source_document_id})
    
    # Mock data write
    if neo4j_client.is_mock():
        neo4j_client.mock_nodes[hid] = {
            "id": hid,
            "label": "Highlight",
            "text": request.text,
            "page": request.page,
            "created_at": created_at
        }
        neo4j_client.mock_edges.append({"from": hid, "to": request.source_document_id, "type": "EXTRACTED_FROM"})
        
    # Execute AI concept-linking
    run_concept_linking_for_highlight(hid, request.text, request.source_document_id)
    
    return {
        "id": hid,
        "text": request.text,
        "page": request.page,
        "created_at": created_at,
        "source_document_id": request.source_document_id
    }

@router.get("/highlights")
def get_highlights(concept_id: Optional[str] = Query(None)):
    if neo4j_client.is_mock():
        # In mock mode, gather matching highlights
        results = []
        for nid, node in neo4j_client.mock_nodes.items():
            if node.get("label") == "Highlight":
                # Filter if concept_id is specified
                if concept_id:
                    # Check if there is a RELATES_TO link
                    has_link = any(
                        edge["from"] == nid and edge["to"] == concept_id and edge["type"] == "RELATES_TO"
                        for edge in neo4j_client.mock_edges
                    )
                    if not has_link:
                        continue
                
                # Fetch source document title
                doc_title = "Document"
                for edge in neo4j_client.mock_edges:
                    if edge["from"] == nid and edge["type"] == "EXTRACTED_FROM":
                        doc = neo4j_client.mock_nodes.get(edge["to"])
                        if doc:
                            doc_title = doc.get("title", "Document")
                
                results.append({
                    "id": node["id"],
                    "text": node["text"],
                    "page": node["page"],
                    "doc_title": doc_title,
                    "created_at": node["created_at"]
                })
        return results

    if concept_id:
        query = """
        MATCH (h:Highlight)-[:RELATES_TO]->(c:Concept {id: $concept_id})
        OPTIONAL MATCH (h)-[:EXTRACTED_FROM]->(d:Document)
        RETURN h.id as id, h.text as text, h.page as page, h.created_at as created_at, d.title as doc_title
        """
        res = neo4j_client.run_query(query, {"concept_id": concept_id})
    else:
        query = """
        MATCH (h:Highlight)
        OPTIONAL MATCH (h)-[:EXTRACTED_FROM]->(d:Document)
        RETURN h.id as id, h.text as text, h.page as page, h.created_at as created_at, d.title as doc_title
        """
        res = neo4j_client.run_query(query)
        
    return [
        {
            "id": r["id"],
            "text": r["text"],
            "page": r["page"],
            "doc_title": r["doc_title"] or "Unknown PDF",
            "created_at": r["created_at"]
        }
        for r in res
    ]
