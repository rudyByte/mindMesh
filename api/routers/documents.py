import io
import uuid
import datetime
import logging
from fastapi import APIRouter, UploadFile, File, BackgroundTasks, HTTPException
from pydantic import BaseModel
from pypdf import PdfReader

from api.utils.neo4j_client import neo4j_client
from api.utils.supabase_client import supabase_client
from api.utils.llm_client import llm_client

router = APIRouter()
logger = logging.getLogger("documents_router")

# Cache to track document processing status in memory for fast lookup
# especially in mock mode or for quick polling
extraction_status_cache = {}

class UploadResponse(BaseModel):
    id: str
    status: str
    title: str

class StatusResponse(BaseModel):
    status: str
    progress_pct: int
    error: str | None = None

def run_extraction_pipeline(doc_id: str, file_bytes: bytes, filename: str):
    extraction_status_cache[doc_id] = {"status": "processing", "progress_pct": 10, "error": None}
    
    try:
        # 1. Parse PDF text
        reader = PdfReader(io.BytesIO(file_bytes))
        text = ""
        for page in reader.pages:
            text += page.extract_text() or ""
        
        text = text.strip()
        if not text:
            raise ValueError("This looks like a scanned PDF — text extraction isn't supported yet.")
            
        extraction_status_cache[doc_id]["progress_pct"] = 30
        
        # 2. Chunk text
        # ~1500 tokens is roughly 6000 characters
        chunk_size = 6000
        overlap = 800
        chunks = []
        start = 0
        while start < len(text):
            end = min(start + chunk_size, len(text))
            chunks.append(text[start:end])
            if end == len(text):
                break
            start += chunk_size - overlap
            
        logger.info(f"Split document into {len(chunks)} chunks.")
        extraction_status_cache[doc_id]["progress_pct"] = 40
        
        # 3. For each chunk, extract nodes/relationships using LLM client
        all_nodes = []
        all_relationships = []
        
        step_increment = 50 / len(chunks) if chunks else 50
        
        for i, chunk in enumerate(chunks):
            try:
                # Call LLM extraction (will use mock extraction if Anthropic key is mock)
                result = llm_client.extract_graph_from_chunk(chunk)
                all_nodes.extend(result.get("nodes", []))
                all_relationships.extend(result.get("relationships", []))
            except Exception as e:
                logger.error(f"Error extracting chunk {i} for doc {doc_id}: {e}")
                # Retry once
                try:
                    result = llm_client.extract_graph_from_chunk(chunk)
                    all_nodes.extend(result.get("nodes", []))
                    all_relationships.extend(result.get("relationships", []))
                except Exception:
                    logger.error(f"Retry failed for chunk {i}. Skipping.")
            
            # Update progress
            current_progress = int(40 + (i + 1) * step_increment)
            extraction_status_cache[doc_id]["progress_pct"] = min(90, current_progress)
            
        # 4. Idempotent Merge Writes to Neo4j
        # Deduplicate nodes by normalized name
        unique_nodes = {}
        for node in all_nodes:
            name = node.get("name")
            if not name:
                continue
            norm_name = name.strip().lower()
            if norm_name not in unique_nodes:
                unique_nodes[norm_name] = node
                
        logger.info(f"Extracted {len(unique_nodes)} unique nodes and {len(all_relationships)} relationships.")
        
        # Write nodes to Neo4j
        for node in unique_nodes.values():
            label = node.get("label", "Concept")
            if label not in ["Concept", "Topic", "Keyword", "Paper", "Author", "Institution"]:
                label = "Concept"
            name = node.get("name").strip()
            desc = node.get("description", "").strip()
            
            node_id = str(uuid.uuid4())
            
            # Neo4j query
            query = f"""
            MERGE (n:{label} {{name: $name, doc_id: $doc_id}})
            ON CREATE SET n.id = $id, n.description = $description, n.difficulty_level = 'Beginner'
            ON MATCH SET n.description = CASE WHEN n.description IS NULL OR n.description = '' THEN $description ELSE n.description END
            RETURN n.id as node_id
            """
            res = neo4j_client.run_query(query, {"name": name, "id": node_id, "description": desc, "doc_id": doc_id})
            
            # Capture the resolved node ID (either the new one or the existing one)
            resolved_id = node_id
            if res and res[0].get("node_id"):
                resolved_id = res[0]["node_id"]
            node["resolved_id"] = resolved_id
            
            # Link node to Document
            link_query = f"""
            MATCH (d:Document {{id: $doc_id}})
            MATCH (n:{label} {{id: $node_id}})
            MERGE (d)-[:CONTAINS]->(n)
            """
            neo4j_client.run_query(link_query, {"doc_id": doc_id, "node_id": resolved_id})

            # Also seed to mock store if in mock mode
            if neo4j_client.is_mock():
                neo4j_client.mock_nodes[resolved_id] = {
                    "id": resolved_id,
                    "label": label,
                    "name": name,
                    "description": desc,
                    "difficulty_level": "Beginner",
                    "doc_id": doc_id
                }

        # Write relationships to Neo4j
        for rel in all_relationships:
            from_name = rel.get("from")
            to_name = rel.get("to")
            rel_type = rel.get("type", "RELATED_TO").strip()
            
            if not from_name or not to_name:
                continue
                
            if rel_type not in ["PREREQUISITE_OF", "RELATED_TO", "EXTENDS", "CONTRADICTS", "USES_METHOD", "DEPENDS_ON", "CITES", "AUTHORED_BY", "AFFILIATED_WITH", "MENTIONS", "HAS_KEYWORD"]:
                rel_type = "RELATED_TO"
                
            query = f"""
            MATCH (a {{name: $from_name, doc_id: $doc_id}})
            MATCH (b {{name: $to_name, doc_id: $doc_id}})
            MERGE (a)-[r:{rel_type}]->(b)
            """
            neo4j_client.run_query(query, {"from_name": from_name, "to_name": to_name, "doc_id": doc_id})
            
            # Also seed to mock store if in mock mode
            if neo4j_client.is_mock():
                # Find matched nodes in mock for this document namespace
                from_id = None
                to_id = None
                for nid, n in neo4j_client.mock_nodes.items():
                    if n.get("doc_id") == doc_id:
                        if n.get("name", "").lower() == from_name.lower():
                            from_id = nid
                        if n.get("name", "").lower() == to_name.lower():
                            to_id = nid
                if from_id and to_id:
                    neo4j_client.mock_edges.append({
                        "from": from_id,
                        "to": to_id,
                        "type": rel_type
                    })
                    
        # Update status to done
        extraction_status_cache[doc_id] = {"status": "done", "progress_pct": 100, "error": None}
        
        # Save completed status to Neo4j node
        neo4j_client.run_query(
            "MATCH (d:Document {id: $doc_id}) SET d.status = 'done', d.progress_pct = 100",
            {"doc_id": doc_id}
        )
        logger.info(f"Extraction pipeline completed successfully for document {doc_id}.")
        
    except Exception as e:
        logger.error(f"Extraction failed for document {doc_id}: {e}")
        error_msg = str(e)
        extraction_status_cache[doc_id] = {"status": "error", "progress_pct": 100, "error": error_msg}
        neo4j_client.run_query(
            "MATCH (d:Document {id: $doc_id}) SET d.status = 'error', d.error_msg = $error",
            {"doc_id": doc_id, "error": error_msg}
        )

@router.post("/documents/upload", response_model=UploadResponse)
async def upload_document(background_tasks: BackgroundTasks, file: UploadFile = File(...)):
    if not file.filename.endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF documents are supported.")
        
    try:
        # Clear all cached data, previous uploads, embeddings, vector-store entries, and session memory
        extraction_status_cache.clear()
        
        # Clear files from storage
        try:
            supabase_client.clear_bucket("documents")
        except Exception as e:
            logger.error(f"Failed to clear storage bucket: {e}")

        if neo4j_client.is_mock():
            # Clear all mock nodes and edges from the mock database
            neo4j_client.mock_nodes.clear()
            neo4j_client.mock_edges.clear()
        else:
            # Delete all nodes and relationships in the Neo4j database
            neo4j_client.run_query("MATCH (n) DETACH DELETE n")

        # Read file bytes
        file_bytes = await file.read()
        
        # Generate unique document ID
        doc_id = str(uuid.uuid4())
        path = f"uploads/{doc_id}_{file.filename}"
        
        # 1. Upload to Supabase Storage (will save locally in mock mode)
        storage_url = supabase_client.upload_file("documents", path, file_bytes)
        
        # 2. Write Document node to Neo4j
        upload_date = datetime.datetime.now().isoformat()
        query = """
        MERGE (d:Document {id: $id})
        ON CREATE SET d.title = $title, d.type = 'pdf', d.upload_date = $upload_date, 
                      d.storage_url = $storage_url, d.status = 'processing', d.progress_pct = 10
        RETURN d
        """
        neo4j_client.run_query(query, {
            "id": doc_id,
            "title": file.filename,
            "upload_date": upload_date,
            "storage_url": storage_url
        })
        
        # Set initial status in cache
        extraction_status_cache[doc_id] = {"status": "processing", "progress_pct": 10, "error": None}
        
        # 3. Trigger background task
        background_tasks.add_task(run_extraction_pipeline, doc_id, file_bytes, file.filename)
        
        return UploadResponse(id=doc_id, status="processing", title=file.filename)
        
    except Exception as e:
        logger.error(f"Failed to upload document: {e}")
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")

@router.get("/documents/{id}/status", response_model=StatusResponse)
def get_document_status(id: str):
    # Check cache first
    status = extraction_status_cache.get(id)
    if status:
        return StatusResponse(**status)
        
    # Check database next
    query = "MATCH (d:Document {id: $id}) RETURN d.status as status, d.progress_pct as progress_pct, d.error_msg as error_msg"
    res = neo4j_client.run_query(query, {"id": id})
    if res:
        record = res[0]
        return StatusResponse(
            status=record.get("status") or "processing",
            progress_pct=record.get("progress_pct") or 10,
            error=record.get("error_msg")
        )
        
    raise HTTPException(status_code=404, detail="Document not found.")

@router.get("/documents/{id}/graph")
def get_document_graph(id: str):
    if neo4j_client.is_mock():
        # Find all mock nodes containing relationships with this document ID
        doc_node_ids = set()
        for edge in neo4j_client.mock_edges:
            if edge["from"] == id and edge["type"] == "CONTAINS":
                doc_node_ids.add(edge["to"])
        
        # If the document is the initial placeholder "doc-1" and has no CONTAINS relationships,
        # fallback to returning all pre-seeded ML concepts (excluding the Document node itself)
        if not doc_node_ids and id == "doc-1":
            ml_nodes = [n for n in neo4j_client.mock_nodes.values() if n.get("label") != "Document"]
            ml_node_ids = {n["id"] for n in ml_nodes}
            ml_edges = [
                e for e in neo4j_client.mock_edges 
                if e["type"] != "CONTAINS" and e["from"] in ml_node_ids and e["to"] in ml_node_ids
            ]
            return {"nodes": ml_nodes, "edges": ml_edges}
            
        # Return only the nodes and edges for this specific document
        doc_nodes = [n for nid, n in neo4j_client.mock_nodes.items() if nid in doc_node_ids]
        doc_edges = [
            e for e in neo4j_client.mock_edges 
            if e["type"] != "CONTAINS" and e["from"] in doc_node_ids and e["to"] in doc_node_ids
        ]
        return {"nodes": doc_nodes, "edges": doc_edges}
        
    # Fetch nodes in the document
    nodes_query = """
    MATCH (d:Document {id: $doc_id})-[:CONTAINS]->(n)
    RETURN labels(n)[0] as label, n.id as id, n.name as name, n.description as description, n.difficulty_level as difficulty_level
    """
    nodes_res = neo4j_client.run_query(nodes_query, {"doc_id": id})
    
    # Fetch edges between nodes in the document
    edges_query = """
    MATCH (d:Document {id: $doc_id})-[:CONTAINS]->(n)
    MATCH (d)-[:CONTAINS]->(m)
    MATCH (n)-[r]->(m)
    RETURN n.id as from_id, m.id as to_id, type(r) as type
    """
    edges_res = neo4j_client.run_query(edges_query, {"doc_id": id})
    
    nodes = []
    for r in nodes_res:
        nodes.append({
            "id": r["id"],
            "label": r["label"],
            "name": r["name"],
            "description": r.get("description", ""),
            "difficulty_level": r.get("difficulty_level", "Beginner")
        })
        
    edges = []
    for r in edges_res:
        edges.append({
            "from": r["from_id"],
            "to": r["to_id"],
            "type": r["type"]
        })
        
    return {"nodes": nodes, "edges": edges}

@router.get("/documents/{id}/text")
def get_document_text(id: str):
    query = "MATCH (d:Document {id: $id}) RETURN d.title as title, d.storage_url as url"
    res = neo4j_client.run_query(query, {"id": id})
    if not res:
        raise HTTPException(status_code=404, detail="Document not found.")
    
    try:
        title = res[0]["title"]
        path = f"uploads/{id}_{title}"
        file_bytes = supabase_client.download_file("documents", path)
        
        reader = PdfReader(io.BytesIO(file_bytes))
        text = ""
        for page in reader.pages:
            text += page.extract_text() or ""
        return {"text": text}
    except Exception as e:
        logger.error(f"Failed to fetch or parse PDF bytes for document {id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch or parse document text: {str(e)}")
