import io
import os
import uuid
import datetime
import logging
import json
from typing import Optional
from concurrent.futures import ThreadPoolExecutor, as_completed
from fastapi import APIRouter, UploadFile, File, BackgroundTasks, HTTPException, Query
from pydantic import BaseModel
from pypdf import PdfReader

from server.utils.neo4j_client import neo4j_client
from server.utils.supabase_client import supabase_client
from server.utils.vercel_blob_client import vercel_blob_client
from server.utils.llm_client import llm_client, calculate_entity_quality, singularize_concept_name, normalize_and_clean_concept_name, GENERIC_BLACKLIST
from server.utils.embedding_client import embedding_client, cosine_similarity
from server.utils.sequence_parser import parse_learning_sequences
from server.utils.text_cleaner import clean_pdf_text_from_bytes, extract_pdf_text_with_metadata
from server.config import config
import re

router = APIRouter()
logger = logging.getLogger("documents_router")

# Cache to track document processing status in memory for fast lookup
# especially in mock mode or for quick polling
extraction_status_cache = {}

# Chunked upload constants
CHUNK_SIZE = 2.5 * 1024 * 1024  # 2.5MB per chunk (safe margin under Vercel's 4.5MB limit)

# In-memory storage for chunked upload sessions
# Key: upload_id, Value: {chunks: {index: bytes}, total: int, filename: str, ..., created_at: float}
chunked_uploads: dict[str, dict] = {}

MAX_CHUNK_AGE_SECONDS = 600  # 10 minutes — clean up orphaned uploads older than this


def _chunk_meta_path(upload_id: str) -> str:
    return f"chunked/{upload_id}_meta.json"


def _chunk_part_path(upload_id: str, chunk_index: int) -> str:
    return f"chunked/{upload_id}_{chunk_index}.part"


def _blob_path_from_storage_url(url: str) -> Optional[str]:
    if not url:
        return None
    if url.startswith("vercel-blob://"):
        return url.replace("vercel-blob://", "", 1)
    if ".blob.vercel-storage.com/" in url:
        try:
            from urllib.parse import urlparse, unquote
            parsed = urlparse(url)
            return unquote(parsed.path.lstrip("/"))
        except Exception:
            return None
    return None


def _json_blob_path(kind: str, key: str) -> str:
    safe_key = re.sub(r"[^a-zA-Z0-9_.-]", "_", key)
    return f"state/{kind}/{safe_key}.json"


def _save_json_state(kind: str, key: str, payload: dict | list) -> None:
    if not vercel_blob_client.is_configured():
        return
    vercel_blob_client.put(
        _json_blob_path(kind, key),
        json.dumps(payload).encode("utf-8"),
        "application/json",
    )


def _load_json_state(kind: str, key: str):
    if not vercel_blob_client.is_configured():
        return None
    try:
        raw = vercel_blob_client.get(_json_blob_path(kind, key))
        return json.loads(raw.decode("utf-8"))
    except Exception:
        return None


def _public_node(node: dict) -> dict:
    """Return a UI/API-safe node copy without heavy internal vectors."""
    public = dict(node)
    public.pop("embedding", None)
    if not public.get("name") and public.get("title"):
        public["name"] = public["title"]
    return public


def _save_doc_status(
    doc_id: str,
    status: str,
    progress_pct: int,
    error: Optional[str] = None,
    session_id: Optional[str] = None,
    failed_chunks: Optional[int] = None,
    total_chunks: Optional[int] = None,
    extraction_mode: Optional[str] = None,
    ocr_used: Optional[bool] = None,
    ocr_confidence: Optional[float] = None,
) -> None:
    previous = extraction_status_cache.get(doc_id) or _load_json_state("doc-status", doc_id) or {}
    payload = {
        "id": doc_id,
        "session_id": session_id,
        "status": status,
        "progress_pct": progress_pct,
        "error": error,
        "failed_chunks": failed_chunks if failed_chunks is not None else previous.get("failed_chunks", 0),
        "total_chunks": total_chunks if total_chunks is not None else previous.get("total_chunks", 0),
        "extraction_mode": extraction_mode or previous.get("extraction_mode"),
        "ocr_used": ocr_used if ocr_used is not None else previous.get("ocr_used", False),
        "ocr_confidence": ocr_confidence if ocr_confidence is not None else previous.get("ocr_confidence"),
    }
    extraction_status_cache[doc_id] = {
        "status": payload["status"],
        "progress_pct": payload["progress_pct"],
        "error": payload["error"],
        "failed_chunks": payload["failed_chunks"],
        "total_chunks": payload["total_chunks"],
        "extraction_mode": payload["extraction_mode"],
        "ocr_used": payload["ocr_used"],
        "ocr_confidence": payload["ocr_confidence"],
    }
    _save_json_state("doc-status", doc_id, payload)


def _save_session_doc(session_id: Optional[str], doc: dict) -> None:
    if not session_id:
        return
    docs = _load_json_state("session-docs", session_id) or []
    docs = [d for d in docs if d.get("id") != doc.get("id")]
    docs.insert(0, doc)
    _save_json_state("session-docs", session_id, docs)


def _persist_mock_session_graph(session_id: Optional[str]) -> None:
    if not session_id or not neo4j_client.is_mock():
        return
    nodes = []
    node_ids = set()
    for nid, n in neo4j_client.mock_nodes.items():
        if n.get("session_id") == session_id and n.get("label") not in ["Document", "Note", "Highlight", "Citation"]:
            node = _public_node(n)
            nodes.append(node)
            node_ids.add(nid)
    edges = [
        e for e in neo4j_client.mock_edges
        if e.get("session_id") == session_id and e.get("type") != "CONTAINS"
    ]
    level_y = {"foundation": -220, "core": 0, "advanced": 220}
    buckets: dict[str, list[dict]] = {"foundation": [], "core": [], "advanced": []}
    for node in nodes:
        lvl = (node.get("level") or "core").lower()
        if lvl not in buckets:
            lvl = "core"
            node["level"] = lvl
        buckets[lvl].append(node)
    for lvl, bucket in buckets.items():
        count = max(1, len(bucket))
        for i, node in enumerate(bucket):
            node.setdefault("y", level_y[lvl])
            node.setdefault("x", (i - (count - 1) / 2) * 150)
    _save_json_state("session-graph", session_id, {"nodes": nodes, "edges": edges})


def _save_chunk_session(upload_id: str, session: dict) -> None:
    """Persist chunk metadata so Vercel serverless instances can share it."""
    meta = {k: v for k, v in session.items() if k != "chunks"}
    payload = json.dumps(meta).encode("utf-8")
    if vercel_blob_client.is_configured():
        vercel_blob_client.put(_chunk_meta_path(upload_id), payload, "application/json")
    else:
        supabase_client.upload_file(
            "documents",
            _chunk_meta_path(upload_id),
            payload,
            content_type="application/json",
        )


def _load_chunk_session(upload_id: str) -> Optional[dict]:
    if upload_id in chunked_uploads:
        return chunked_uploads[upload_id]
    try:
        if vercel_blob_client.is_configured():
            raw = vercel_blob_client.get(_chunk_meta_path(upload_id))
        else:
            raw = supabase_client.download_file("documents", _chunk_meta_path(upload_id))
        meta = json.loads(raw.decode("utf-8"))
        meta["chunks"] = {}
        chunked_uploads[upload_id] = meta
        return meta
    except Exception as e:
        logger.warning(f"Chunk session {upload_id} not found in persistent storage: {e}")
        return None


def _delete_chunk_session(upload_id: str, total_chunks: int) -> None:
    chunked_uploads.pop(upload_id, None)
    try:
        if vercel_blob_client.is_configured():
            vercel_blob_client.delete(_chunk_meta_path(upload_id))
        else:
            supabase_client.delete_file("documents", _chunk_meta_path(upload_id))
    except Exception as e:
        logger.warning(f"Failed to delete chunk metadata for {upload_id}: {e}")
    for i in range(total_chunks):
        try:
            if vercel_blob_client.is_configured():
                vercel_blob_client.delete(_chunk_part_path(upload_id, i))
            else:
                supabase_client.delete_file("documents", _chunk_part_path(upload_id, i))
        except Exception as e:
            logger.warning(f"Failed to delete chunk {i} for {upload_id}: {e}")


class UploadResponse(BaseModel):
    id: str
    status: str
    title: str

class StatusResponse(BaseModel):
    status: str
    progress_pct: int
    error: str | None = None
    failed_chunks: int = 0
    total_chunks: int = 0
    extraction_mode: str | None = None
    ocr_used: bool = False
    ocr_confidence: float | None = None

def is_acronym_of(a: str, p: str) -> bool:
    a_clean = re.sub(r'[^a-zA-Z]', '', a).upper()
    p_words = [w for w in re.sub(r'[^a-zA-Z\s]', ' ', p).split() if w]
    
    if not (2 <= len(a_clean) <= 6) or len(p_words) < 2:
        return False
        
    initials = "".join([w[0].upper() for w in p_words if w])
    if a_clean == initials:
        return True
        
    important_initials = "".join([w[0].upper() for w in p_words if w.lower() not in ["of", "and", "in", "from", "for", "with", "the"]])
    if a_clean == important_initials:
        return True
        
    return False

def are_semantically_similar(name1: str, name2: str) -> bool:
    n1 = name1.lower().strip()
    n2 = name2.lower().strip()
    if n1 == n2:
        return True
        
    # Check acronyms
    if is_acronym_of(n1, n2) or is_acronym_of(n2, n1):
        return True
        
    def normalize_word(w):
        w = w.rstrip(',.;:()[]{}-_')
        if w.endswith('ies'):
            w = w[:-3] + 'y'
        elif w.endswith('es') and not w.endswith('see'):
            w = w[:-2]
        elif w.endswith('s') and not w.endswith('ss') and not w.endswith('us') and not w.endswith('is'):
            w = w[:-1]
        if w.endswith('ing'):
            w = w[:-3]
        return w

    n1_norm = " ".join([normalize_word(w) for w in n1.replace('-', ' ').split()])
    n2_norm = " ".join([normalize_word(w) for w in n2.replace('-', ' ').split()])
    
    if n1_norm == n2_norm:
        return True
        
    w1 = set(n1_norm.split())
    w2 = set(n2_norm.split())
    if not w1 or not w2:
        return False
        
    intersection = w1.intersection(w2)
    union = w1.union(w2)
    jaccard = len(intersection) / len(union)
    if jaccard >= 0.6:
        return True
        
    if len(n1) > 4 and len(n2) > 4:
        if n1 in n2 or n2 in n1:
            shorter, longer = (n1, n2) if len(n1) < len(n2) else (n2, n1)
            if len(shorter.split()) >= 1 and shorter.split()[0] in longer.split():
                return True
                
    return False

def is_concept_in_text(concept_name: str, text_content: str) -> bool:
    if not concept_name:
        return False
    cleaned_name = concept_name.strip()
    escaped = re.escape(cleaned_name)
    if cleaned_name.lower().endswith('y'):
        base = escaped[:-1]
        pattern = r'\b' + base + r'(y|ies)\b'
    elif cleaned_name.lower().endswith('s'):
        pattern = r'\b' + escaped + r'\b'
    else:
        pattern = r'\b' + escaped + r'(s|es)?\b'
    try:
        return bool(re.search(pattern, text_content, re.IGNORECASE))
    except Exception:
        return cleaned_name.lower() in text_content.lower()

def enrich_node_descriptions(canonical_nodes: list, full_text: str):
    cleaned_text = re.sub(r'\s+', ' ', full_text)
    
    for node in canonical_nodes:
        desc = node.get("description", "").strip()
        name = node.get("name", "").strip()
        
        if not desc or len(desc.split()) < 12 or any(p in desc.lower() for p in ["placeholder", "no description", "extracted yet"]):
            matches = list(re.finditer(rf'\b{re.escape(name)}\b', cleaned_text, re.IGNORECASE))
            if not matches:
                idx = cleaned_text.lower().find(name.lower())
                if idx != -1:
                    class FakeMatch:
                        def __init__(self, start, end):
                            self._start = start
                            self._end = end
                        def start(self): return self._start
                        def end(self): return self._end
                    matches = [FakeMatch(idx, idx + len(name))]
            
            found_desc = ""
            for match in matches:
                start = max(0, match.start() - 150)
                end = min(len(cleaned_text), match.end() + 250)
                window = cleaned_text[start:end]
                
                sentences = re.split(r'(?<=[.!?])\s+', window)
                for sent in sentences:
                    sent = sent.strip()
                    if name.lower() in sent.lower():
                        sent_low = sent.lower()
                        is_def = any(pattern in sent_low for pattern in [
                            " is ", " are ", " refers to ", " is defined as ", " represents ", " denotes ", " refers ", " is a ", " is an "
                        ])
                        if is_def and len(sent.split()) >= 10:
                            found_desc = sent
                            break
                if found_desc:
                    break
                    
            if not found_desc and matches:
                first_match = matches[0]
                start = max(0, first_match.start() - 100)
                end = min(len(cleaned_text), first_match.end() + 200)
                window = cleaned_text[start:end]
                sentences = re.split(r'(?<=[.!?])\s+', window)
                for sent in sentences:
                    sent = sent.strip()
                    if name.lower() in sent.lower() and len(sent.split()) >= 8:
                        found_desc = sent
                        break
            
            if found_desc:
                found_desc = re.sub(r'\s+', ' ', found_desc).strip()
                if len(found_desc) > 250:
                    found_desc = found_desc[:247] + "..."
                if found_desc:
                    found_desc = found_desc[0].upper() + found_desc[1:]
                node["description"] = found_desc
            elif not desc:
                node["description"] = f"Key concept of {name} extracted from the document."

def cluster_and_merge_nodes(nodes: list) -> tuple[list, dict]:
    clusters = []
    threshold = getattr(config, "EMBEDDING_SIMILARITY_THRESHOLD", 0.87)
    
    for node in nodes:
        name = node.get("name")
        if not name:
            continue
        node_embedding = node.get("embedding")
        if not node_embedding:
            node_embedding = embedding_client.embed_node(node)
            node["embedding"] = node_embedding
        matched = False
        for cluster in clusters:
            rep_node = cluster[0]
            rep_embedding = rep_node.get("embedding")
            if not rep_embedding:
                rep_embedding = embedding_client.embed_node(rep_node)
                rep_node["embedding"] = rep_embedding
            full_emb_sim = cosine_similarity(node_embedding, rep_embedding)
            name_emb_sim = cosine_similarity(
                embedding_client.embed_text(name),
                embedding_client.embed_text(rep_node["name"]),
            )
            emb_sim = max(full_emb_sim, name_emb_sim)
            acronym_match = is_acronym_of(name, rep_node["name"]) or is_acronym_of(rep_node["name"], name)
            lexical_match = are_semantically_similar(name, rep_node["name"])
            if acronym_match or emb_sim >= threshold or (lexical_match and emb_sim >= 0.72):
                cluster.append(node)
                matched = True
                break
        if not matched:
            clusters.append([node])
            
    canonical_nodes = []
    name_mapping = {}
    
    for cluster in clusters:
        rep = cluster[0]
        for node in cluster:
            if node.get("is_existing") and not rep.get("is_existing"):
                rep = node
                continue
            elif rep.get("is_existing") and not node.get("is_existing"):
                continue

            rep_label = rep.get("label", "Concept")
            node_label = node.get("label", "Concept")
            
            label_order = ["Topic", "Paper", "Author", "Concept", "Keyword"]
            rep_priority = label_order.index(rep_label) if rep_label in label_order else 99
            node_priority = label_order.index(node_label) if node_label in label_order else 99
            
            if node_priority < rep_priority:
                rep = node
            elif node_priority == rep_priority:
                if len(node["name"]) > len(rep["name"]):
                    rep = node
                elif node["name"].istitle() and not rep["name"].istitle():
                    rep = node
                    
        descriptions = []
        seen_descs = set()
        for node in cluster:
            desc = node.get("description", "").strip()
            if desc and desc not in seen_descs:
                descriptions.append(desc)
                seen_descs.add(desc)
        
        canonical_desc = " ".join(descriptions)
        if len(canonical_desc) > 300:
            canonical_desc = canonical_desc[:297] + "..."
            
        canonical_node = {
            "label": rep.get("label", "Concept"),
            "name": rep["name"].strip(),
            "description": canonical_desc,
            "difficulty_level": rep.get("difficulty_level", "Beginner"),
            "embedding": rep.get("embedding") or embedding_client.embed_node(rep)
        }
        for k, v in rep.items():
            if k not in canonical_node:
                canonical_node[k] = v
        canonical_nodes.append(canonical_node)
        
        for node in cluster:
            name_mapping[node["name"].lower().strip()] = canonical_node["name"]
            
    return canonical_nodes, name_mapping


def _sentence_for_term(text: str, term: str) -> str:
    clean = re.sub(r"\s+", " ", text)
    for sentence in re.split(r"(?<=[.!?])\s+", clean):
        if term.lower() in sentence.lower() and len(sentence.split()) >= 6:
            return sentence[:260]
    return f"{term} is a key concept discussed in this document."


def _build_fast_grounded_graph(text: str, filename: str, main_topic_info: dict) -> dict:
    return _build_dynamic_fallback_graph(text, filename, main_topic_info)


def _sample_document_text(text: str, max_chars: int = 9000) -> str:
    clean = re.sub(r"\s+", " ", text).strip()
    if len(clean) <= max_chars:
        return clean
    third = max_chars // 3
    mid_start = max(0, len(clean) // 2 - third // 2)
    return "\n\n".join([clean[:third], clean[mid_start:mid_start + third], clean[-third:]])


def _build_dynamic_fallback_graph(text: str, filename: str, main_topic_info: dict) -> dict:
    """LLM-free, document-local hierarchy. No fixed PDFs or domain templates."""
    topic_name = main_topic_info.get("name") or filename.rsplit(".", 1)[0].replace("_", " ").replace("-", " ").title()
    topic_desc = main_topic_info.get("description") or f"{topic_name} is the main topic extracted from {filename}."
    stop = {
        "abstract", "introduction", "conclusion", "references", "figure", "table", "chapter", "section",
        "page", "pages", "objective", "objectives", "procedure", "result", "results", "discussion",
        "example", "examples", "question", "questions", "answer", "answers", "exercise", "exercises",
        "using", "use", "used", "attach", "attached", "connect", "connected", "disconnect", "record",
        "observe", "calculate", "write", "last", "next", "first", "second", "third", "green", "red",
        "blue", "black", "white", "wire", "wires", "january", "february", "march", "april", "may",
        "june", "july", "august", "september", "october", "november", "december"
    } | GENERIC_BLACKLIST
    phrase_counts: dict[str, int] = {}
    for pattern in [
        r"\b[A-Z][A-Za-z][A-Za-z'’/-]*(?:\s+[A-Z][A-Za-z][A-Za-z'’/-]*){0,3}\b",
        r"\b[a-z][a-z]{3,}(?:\s+[a-z][a-z]{3,}){1,3}\b",
    ]:
        for raw in re.findall(pattern, text):
            name = normalize_and_clean_concept_name(raw)
            if not name or len(name) > 40 or len(name.split()) > 4:
                continue
            low = name.lower()
            if low in stop or any(w in stop for w in low.split()):
                continue
            if re.search(r"\b(using|attach|connect|record|observe|calculate|step|last|next)\b", low):
                continue
            if len(name.split()) == 1 and low.endswith(("ing", "ed")):
                continue
            if calculate_entity_quality(name, "Concept") <= 0.7:
                continue
            phrase_counts[name] = phrase_counts.get(name, 0) + 1

    ranked = sorted(phrase_counts.items(), key=lambda item: (item[1], len(item[0])), reverse=True)[:14]
    nodes = [{
        "label": "Topic",
        "name": topic_name,
        "description": topic_desc,
        "difficulty_level": "Beginner",
        "level": "core",
    }]
    for i, (name, _) in enumerate(ranked):
        nodes.append({
            "label": "Concept",
            "name": name,
            "description": _sentence_for_term(text, name),
            "difficulty_level": "Beginner" if i < 5 else "Intermediate",
            "level": "foundation" if i < 4 else ("advanced" if i > 9 else "core"),
        })

    rels = []
    seen = set()
    for node in nodes[1:]:
        level = node.get("level")
        rel = "PREREQUISITE" if level == "foundation" else ("EXTENDS" if level == "advanced" else "CONTAINS")
        source, target = (node["name"], topic_name) if level == "foundation" else (topic_name, node["name"])
        key = (source, target, rel)
        if key not in seen:
            seen.add(key)
            rels.append({"from": source, "to": target, "type": rel})

    return {"nodes": nodes, "relationships": rels}



def run_extraction_pipeline(doc_id: str, file_bytes: bytes, filename: str, session_id: str):
    failed_chunks = 0
    total_chunks = 0
    text_meta = {"ocr_used": False, "ocr_confidence": None}
    _save_doc_status(doc_id, "processing", 10, None, session_id)
    
    try:
        # 1. Parse and clean PDF text; fall back to OCR for scanned PDFs.
        text, _, text_meta = extract_pdf_text_with_metadata(file_bytes)
        
        if not text:
            ocr_error = text_meta.get("ocr_error")
            if ocr_error:
                raise ValueError(f"This looks like a scanned PDF, but OCR could not run: {ocr_error}")
            raise ValueError("This PDF has no extractable text.")
            
        _save_doc_status(
            doc_id,
            "processing",
            30,
            None,
            session_id,
            ocr_used=bool(text_meta.get("ocr_used")),
            ocr_confidence=text_meta.get("ocr_confidence"),
        )
        
        # Identify main topic of the document
        main_topic_info = llm_client.identify_main_topic(text[:15000], filename)
        logger.info(f"Identified main topic: {main_topic_info}")
        
        # 2. Chunk full document. No large-document shortcut: every chunk is read.
        # ~1500 tokens is roughly 6000 characters; overlap preserves cross-page concepts.
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
            
        total_chunks = len(chunks)
        failed_chunks = 0
        logger.info(f"Split document into {total_chunks} chunks.")
        _save_doc_status(
            doc_id,
            "processing",
            40,
            None,
            session_id,
            failed_chunks=0,
            total_chunks=total_chunks,
            extraction_mode="full_document_chunked",
        )
        
        # 3. For each chunk, extract nodes/relationships using LLM client
        all_nodes = []
        all_relationships = []
        use_serverless_local_extraction = bool(
            os.getenv("VERCEL") and getattr(config, "SERVERLESS_LOCAL_EXTRACTION", True)
        )

        def extract_one_chunk(chunk_index: int, chunk_text: str) -> tuple[list, list, bool]:
            if use_serverless_local_extraction:
                result = _build_dynamic_fallback_graph(
                    chunk_text,
                    f"{filename} chunk {chunk_index + 1}",
                    main_topic_info,
                )
                extracted_nodes = result.get("nodes", [])
                extracted_rels = result.get("relationships", [])
                for node in extracted_nodes:
                    node["name"] = normalize_and_clean_concept_name(node.get("name", ""))
                for rel in extracted_rels:
                    rel["from"] = normalize_and_clean_concept_name(rel.get("from", ""))
                    rel["to"] = normalize_and_clean_concept_name(rel.get("to", ""))
                return extracted_nodes, extracted_rels, False

            try:
                result = llm_client.extract_graph_from_chunk(chunk_text, include_prerequisites=False)
                chunk_failed = False
            except Exception as first_error:
                logger.error(f"Error extracting chunk {chunk_index} for doc {doc_id}: {first_error}")
                if "timeout" in str(first_error).lower() or "timed out" in str(first_error).lower():
                    result = _build_dynamic_fallback_graph(
                        chunk_text,
                        f"{filename} chunk {chunk_index + 1}",
                        main_topic_info,
                    )
                    chunk_failed = True
                    extracted_nodes = result.get("nodes", [])
                    extracted_rels = result.get("relationships", [])
                    for node in extracted_nodes:
                        node["name"] = normalize_and_clean_concept_name(node.get("name", ""))
                    for rel in extracted_rels:
                        rel["from"] = normalize_and_clean_concept_name(rel.get("from", ""))
                        rel["to"] = normalize_and_clean_concept_name(rel.get("to", ""))
                    return extracted_nodes, extracted_rels, chunk_failed
                try:
                    result = llm_client.extract_graph_from_chunk(chunk_text, include_prerequisites=False)
                    chunk_failed = False
                except Exception as retry_error:
                    logger.error(f"Retry failed for chunk {chunk_index} in doc {doc_id}: {retry_error}")
                    # Per-chunk local fallback only; never replace the whole document graph.
                    result = _build_dynamic_fallback_graph(
                        chunk_text,
                        f"{filename} chunk {chunk_index + 1}",
                        main_topic_info,
                    )
                    chunk_failed = True

            extracted_nodes = result.get("nodes", [])
            extracted_rels = result.get("relationships", [])

            for node in extracted_nodes:
                node["name"] = normalize_and_clean_concept_name(node.get("name", ""))
            for rel in extracted_rels:
                rel["from"] = normalize_and_clean_concept_name(rel.get("from", ""))
                rel["to"] = normalize_and_clean_concept_name(rel.get("to", ""))

            return extracted_nodes, extracted_rels, chunk_failed

        if chunks:
            max_workers = min(4, total_chunks)
            completed_chunks = 0
            logger.info(f"Using full-document chunk extraction for {filename}: {total_chunks} chunks, {max_workers} workers")
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                futures = {
                    executor.submit(extract_one_chunk, i, chunk): i
                    for i, chunk in enumerate(chunks)
                }
                for future in as_completed(futures):
                    i = futures[future]
                    try:
                        extracted_nodes, extracted_rels, chunk_failed = future.result()
                        all_nodes.extend(extracted_nodes)
                        all_relationships.extend(extracted_rels)
                        if chunk_failed:
                            failed_chunks += 1
                    except Exception as e:
                        # Defensive: extract_one_chunk should already fallback, but status must never lie.
                        logger.error(f"Unhandled chunk worker failure for chunk {i} in doc {doc_id}: {e}")
                        failed_chunks += 1
                    completed_chunks += 1
                    current_progress = int(40 + (completed_chunks / total_chunks) * 50)
                    _save_doc_status(
                        doc_id,
                        "processing",
                        min(90, current_progress),
                        None,
                        session_id,
                        failed_chunks=failed_chunks,
                        total_chunks=total_chunks,
                        extraction_mode="full_document_chunked",
                    )
        else:
            _save_doc_status(
                doc_id,
                "processing",
                90,
                None,
                session_id,
                failed_chunks=0,
                total_chunks=0,
                extraction_mode="full_document_chunked",
            )
            
        # Implement explicit Regex/Stop-Word Blacklist for broken or non-academic terms
        STOP_WORDS_BLACKLIST = {"become", "becomes", "became", "want", "learn", "how", "to", "the", "with", "variabl"}
        all_nodes = [node for node in all_nodes if node.get("name", "").lower() not in STOP_WORDS_BLACKLIST]
        all_relationships = [rel for rel in all_relationships 
                             if rel.get("from", "").lower() not in STOP_WORDS_BLACKLIST 
                             and rel.get("to", "").lower() not in STOP_WORDS_BLACKLIST]

        # Entity Quality Validation Blocker
        if all_nodes:
            low_quality_nodes = []
            for node in all_nodes:
                score = calculate_entity_quality(node.get("name", ""), node.get("label", "Concept"))
                if score <= 0.7:
                    low_quality_nodes.append(node.get("name", ""))
            
            low_quality_ratio = len(low_quality_nodes) / len(all_nodes)
            logger.info(f"Pipeline quality check: Total nodes={len(all_nodes)}, Low-quality={len(low_quality_nodes)} ({low_quality_ratio:.2%})")
            
            if low_quality_ratio > 0.80:
                logger.error(f"Validation failed: {low_quality_ratio:.2%} of extracted nodes are low-quality: {low_quality_nodes[:15]}")
                raise ValueError(
                    f"Graph extraction validation failed: {low_quality_ratio:.1%} of extracted terms are low-quality (exceeds 80% limit). "
                    f"Examples of low-quality terms: {', '.join(low_quality_nodes[:5])}"
                )
            
            # Filter out low-value nodes automatically
            all_nodes = [n for n in all_nodes if calculate_entity_quality(n.get("name", ""), n.get("label", "Concept")) > 0.7]

        # Persistent multi-document mode: never wipe existing graph content on upload.
        # New concepts/papers/authors are merged into the active session/user graph below.
        multi_doc_mode = True

        # 4. Idempotent Merge Writes to Neo4j
        # Prepare the central node
        central_node = {
            "label": "Topic",
            "name": main_topic_info.get("name", "Document Main Topic"),
            "description": main_topic_info.get("description", ""),
            "difficulty_level": "Beginner",
            "level": "core"
        }
        
        # Add central node to the list of nodes
        all_nodes.append(central_node)
        
        # Session-wide node merging: merge current extraction with existing graph nodes
        # so repeated concepts across documents become one connected concept.
        existing_nodes = []
        if session_id:
            try:
                if neo4j_client.is_mock():
                    for mn in neo4j_client.mock_nodes.values():
                        if mn.get("session_id") == session_id and mn.get("label") not in ["Document", "Note", "Highlight", "Citation"]:
                            existing_nodes.append({
                                "label": mn.get("label", "Concept"),
                                "name": mn.get("name") or mn.get("title") or "",
                                "description": mn.get("description", ""),
                                "difficulty_level": mn.get("difficulty_level", "Beginner"),
                                "level": mn.get("level"),
                                "embedding": mn.get("embedding"),
                                "is_existing": True
                            })
                else:
                    query = """
                    MATCH (n)
                    WHERE n.session_id = $session_id AND NOT n:Document AND NOT n:Note AND NOT n:Highlight AND NOT n:Citation
                    RETURN labels(n)[0] as label, coalesce(n.name, n.title) as name, n.description as description, n.difficulty_level as difficulty_level, n.level as level, n.embedding as embedding
                    """
                    res = neo4j_client.run_query(query, {"session_id": session_id})
                    for r in res:
                        existing_nodes.append({
                            "label": r.get("label") or "Concept",
                            "name": r.get("name") or "",
                            "description": r.get("description") or "",
                            "difficulty_level": r.get("difficulty_level") or "Beginner",
                            "level": r.get("level"),
                            "embedding": r.get("embedding"),
                            "is_existing": True
                        })
                logger.info(f"Retrieved {len(existing_nodes)} existing nodes from session {session_id} for persistent graph merging.")
            except Exception as e:
                logger.error(f"Failed to fetch existing session nodes for merging: {e}")

        all_nodes_combined = existing_nodes + all_nodes

        # Run global semantic merging and clustering
        canonical_nodes, name_mapping = cluster_and_merge_nodes(all_nodes_combined)
        current_canonical_names = {
            name_mapping.get(n.get("name", "").lower().strip(), n.get("name", "")).lower().strip()
            for n in all_nodes
            if n.get("name")
        }
        canonical_nodes = [
            n for n in canonical_nodes
            if n.get("name", "").lower().strip() in current_canonical_names
        ]
        
        # Verify that every graph node exists in the current document text
        original_count = len(canonical_nodes)
        
        if not neo4j_client.is_mock():
            canonical_nodes = [
                n for n in canonical_nodes
                if n.get("level") == "foundation" or is_concept_in_text(n.get("name", ""), text)
            ]
            logger.info(f"Filtered out {original_count - len(canonical_nodes)} nodes not present in the document text.")
        else:
            logger.info("[MOCK] Skipping text grounding filter to preserve complete mock graph.")
        
        # Enrich descriptions using document text context
        logger.info("Enriching node descriptions using document text context...")
        enrich_node_descriptions(canonical_nodes, text)

        # Rewrite relationships to use canonical names
        merged_relationships = []
        seen_rels = set()
        for rel in all_relationships:
            from_name = rel.get("from")
            to_name = rel.get("to")
            rel_type = rel.get("type", "RELATED_TO").strip()
            
            # Normalize relationship type
            normalized_type = rel_type.upper().replace("-", "_").replace(" ", "_")
            if normalized_type in ["REQUIRES", "PREREQUISITE", "PREREQUISITE_OF"]:
                normalized_type = "PREREQUISITE_OF"
            elif normalized_type in ["DEPENDS_ON", "DEPENDENCY", "DEPENDENCY_OF"]:
                normalized_type = "DEPENDS_ON"
            elif normalized_type in ["USES", "USES_METHOD", "UTILIZES", "EMPLOY"]:
                normalized_type = "USES"
            elif normalized_type in ["USED_BY"]:
                normalized_type = "USED_BY"
            elif normalized_type in ["USED_FOR", "USE_FOR"]:
                normalized_type = "USED_FOR"
            elif normalized_type in ["EVALUATED_ON", "EVALUATE_ON", "TESTED_ON"]:
                normalized_type = "EVALUATED_ON"
            elif normalized_type in ["EXTENDS", "INHERITS", "SPECIALIZATION_OF"]:
                normalized_type = "EXTENDS"
            elif normalized_type in ["CITES", "REFERENCES", "REFERENCED_BY", "CITES_PAPER"]:
                normalized_type = "CITES"
            elif normalized_type in ["PART_OF", "INCLUDES"]:
                normalized_type = "PART_OF"
            elif normalized_type in ["CONTAINS"]:
                normalized_type = "CONTAINS"
            elif normalized_type in ["CAUSES", "LEADS_TO"]:
                normalized_type = "CAUSES"
            elif normalized_type in ["RELATED_TO", "ASSOCIATED_WITH"]:
                normalized_type = "RELATED_TO"
            elif normalized_type in ["AUTHORED_BY", "AUTHOR_OF"]:
                normalized_type = "AUTHORED_BY"
            elif normalized_type in ["HAS_KEYWORD"]:
                normalized_type = "HAS_KEYWORD"
            else:
                normalized_type = "RELATED_TO"
            
            if not from_name or not to_name:
                continue
                
            canonical_from = name_mapping.get(from_name.lower().strip(), from_name)
            canonical_to = name_mapping.get(to_name.lower().strip(), to_name)
            
            if canonical_from.lower().strip() == canonical_to.lower().strip():
                continue
                
            rel_key = (canonical_from, canonical_to, normalized_type)
            if rel_key not in seen_rels:
                seen_rels.add(rel_key)
                merged_relationships.append({
                    "from": canonical_from,
                    "to": canonical_to,
                    "type": normalized_type
                })
                
        # Rank concepts and keywords by importance (TF-IDF + Degree + Frequency)
        freq_map = {}
        for n in all_nodes:
            name = n.get("name", "").strip().lower()
            canonical_name = name_mapping.get(name, name).strip()
            freq_map[canonical_name] = freq_map.get(canonical_name, 0) + 1

        degree_map = {}
        for rel in merged_relationships:
            f = rel["from"]
            t = rel["to"]
            degree_map[f] = degree_map.get(f, 0) + 1
            degree_map[t] = degree_map.get(t, 0) + 1

        # Calculate true TF-IDF across document chunks
        import math
        tf_map = {}
        df_map = {}
        N = len(chunks) if chunks else 1
        text_lower = text.lower()
        
        for n in canonical_nodes:
            c_name = n["name"]
            c_name_lower = c_name.lower()
            
            # TF: term frequency in full document
            tf_map[c_name] = text_lower.count(c_name_lower)
            
            # DF: document frequency (how many chunks contain it)
            df_count = sum(1 for chunk in chunks if c_name_lower in chunk.lower())
            df_map[c_name] = df_count

        tfidf_map = {}
        for n in canonical_nodes:
            c_name = n["name"]
            tf = tf_map.get(c_name, 0)
            df = df_map.get(c_name, 0)
            # Smooth IDF
            idf = math.log((1 + N) / (1 + df)) + 1
            tfidf_map[c_name] = tf * idf

        concepts_keywords = [n for n in canonical_nodes if n.get("label") in ["Concept", "Keyword", "Method", "Dataset"]]
        other_nodes = [n for n in canonical_nodes if n.get("label") not in ["Concept", "Keyword", "Method", "Dataset"]]

        # Prioritize noun phrases and technical terms
        def get_priority_bonus(name: str) -> float:
            # Check if multi-word phrase (noun phrase)
            if len(name.split()) > 1:
                return 1.5
            # Check if uppercase technical acronym (e.g. DFA, NFA, ZKP)
            if name.isupper() and name.isalpha() and 2 <= len(name) <= 6:
                return 1.5
            return 1.0

        # Sort concepts/keywords by unified score descending
        concepts_keywords.sort(
            key=lambda n: (tfidf_map.get(n["name"], 0) + degree_map.get(n["name"], 0) * 5 + freq_map.get(n["name"], 0) * 10) * get_priority_bonus(n["name"]),
            reverse=True
        )

        # Keep top 80 concepts/keywords/methods/datasets
        kept_concepts_keywords = concepts_keywords[:80]
        kept_names = set(n["name"].lower().strip() for n in kept_concepts_keywords)
        for n in other_nodes:
            kept_names.add(n["name"].lower().strip())

        canonical_nodes = other_nodes + kept_concepts_keywords

        # Filter relationships to only connect kept nodes
        merged_relationships = [
            rel for rel in merged_relationships
            if rel["from"].lower().strip() in kept_names and rel["to"].lower().strip() in kept_names
        ]

        # Ensure graph connectivity (connect isolated nodes/subgraphs to the central node)
        nodes_by_name = {n["name"].lower().strip(): n for n in canonical_nodes}
        
        central_name_lower = central_node["name"].lower().strip()
        resolved_central_name = name_mapping.get(central_name_lower, central_node["name"])
        resolved_central_lower = resolved_central_name.lower().strip()
        
        if resolved_central_lower not in nodes_by_name:
            # Re-insert central node just in case
            canonical_nodes.append(central_node)
            nodes_by_name[resolved_central_lower] = central_node
            
        adj = {name: set() for name in nodes_by_name.keys()}
        for rel in merged_relationships:
            f = rel["from"].lower().strip()
            t = rel["to"].lower().strip()
            if f in adj and t in adj:
                adj[f].add(t)
                adj[t].add(f)
                
        # Find connected components
        visited = set()
        components = []
        for name in nodes_by_name.keys():
            if name not in visited:
                comp = []
                queue = [name]
                visited.add(name)
                while queue:
                    curr = queue.pop(0)
                    comp.append(curr)
                    for neighbor in adj[curr]:
                        if neighbor not in visited:
                            visited.add(neighbor)
                            queue.append(neighbor)
                components.append(comp)
                
        logger.info(f"Connected components before linking: {len(components)}")
        
        # Find index of the component containing the central node
        central_comp_idx = -1
        for idx, comp in enumerate(components):
            if resolved_central_lower in comp:
                central_comp_idx = idx
                break
                
        if central_comp_idx == -1 and components:
            central_comp_idx = 0
            
        # Connect other components to the central component
        final_relationships = list(merged_relationships)
        
        if components:
            for idx, comp in enumerate(components):
                if idx == central_comp_idx:
                    continue
                # Pick node with highest degree in component
                target_node_name = comp[0]
                max_deg = -1
                for node_name in comp:
                    deg = len(adj[node_name])
                    if deg > max_deg:
                        max_deg = deg
                        target_node_name = node_name
                        
                central_canonical_name = nodes_by_name[resolved_central_lower]["name"]
                target_canonical_name = nodes_by_name[target_node_name]["name"]
                
                final_relationships.append({
                    "from": central_canonical_name,
                    "to": target_canonical_name,
                    "type": "RELATED_TO"
                })
                logger.info(f"Connected disconnected component starting with node '{target_canonical_name}' to central topic '{central_canonical_name}'")
                
                # Re-add to adjacency list for deg logs
                f_low = central_canonical_name.lower().strip()
                t_low = target_canonical_name.lower().strip()
                if f_low in adj and t_low in adj:
                    adj[f_low].add(t_low)
                    adj[t_low].add(f_low)
                
        # Remove any randomly extracted Paper nodes from the chunk phase to ensure clean citations
        canonical_nodes = [n for n in canonical_nodes if n.get("label") != "Paper"]
        
        # Always represent the uploaded research document itself as a Paper.
        paper_title = re.sub(r"^[0-9a-fA-F-]{36}_", "", filename)
        paper_title = re.sub(r"\.pdf$", "", paper_title, flags=re.IGNORECASE).strip()
        paper_node = {
            "label": "Paper",
            "name": paper_title or "Uploaded Research Paper",
            "description": f"Source research paper for the extracted knowledge graph: {paper_title}.",
            "year": None,
            "doi": None,
        }
        canonical_nodes.append(paper_node)

        # Generate Prerequisite Relationships via second LLM pass
        logger.info("Running second LLM pass for prerequisite generation...")
        concept_names = [n["name"] for n in canonical_nodes if n.get("label") not in ["Document", "Paper", "Citation", "Note", "Highlight"]]
        prereqs = llm_client.extract_document_prerequisites(concept_names)
        if prereqs:
            logger.info(f"Generated {len(prereqs)} PREREQUISITE relationships.")
            for req in prereqs:
                from_name = req.get("from")
                to_name = req.get("to")
                if from_name and to_name:
                    final_relationships.append({
                        "from": from_name,
                        "to": to_name,
                        "type": "PREREQUISITE_OF"
                    })

        # Dedicated bibliography extraction
        references_text = None
        # Locate references section by searching for "References" or "Bibliography"
        ref_matches = list(re.finditer(r'\n(?:(?:\d+\.?|\[\d+\]|\b(?:IX|IV|V?I{0,3}))\s*)?(?:References|Bibliography)\s*\n', text, re.IGNORECASE))
        if ref_matches:
            last_match = ref_matches[-1]
            references_text = text[last_match.end():].strip()
            # If the extracted text is too long, limit to last 25000 chars to avoid parsing appendices indefinitely
            if len(references_text) > 25000:
                references_text = references_text[:25000]

        if references_text:
            logger.info("Found References section, running dedicated citation extraction...")
            try:
                citations = llm_client.extract_citations(references_text)
                for cit in citations:
                    title = cit.get("title")
                    if not title:
                        continue
                    
                    cit_node = {
                        "label": "Paper",
                        "name": title,
                        "description": f"Reference citation extracted from document: {title}.",
                        "year": cit.get("year"),
                        "venue": cit.get("venue"),
                        "doi": cit.get("doi")
                    }
                    if not any(n.get("name") == title and n.get("label") == "Paper" for n in canonical_nodes):
                        canonical_nodes.append(cit_node)
                    
                    final_relationships.append({
                        "from": paper_node["name"],
                        "to": title,
                        "type": "CITES"
                    })
                    
                    # Create Author nodes and link
                    authors = cit.get("authors", [])
                    if isinstance(authors, list):
                        for author in authors:
                            if not author:
                                continue
                            author_node = {
                                "label": "Author",
                                "name": author,
                                "description": f"Author of the paper '{title}'.",
                                "difficulty_level": "Beginner"
                            }
                            if not any(n.get("name") == author and n.get("label") == "Author" for n in canonical_nodes):
                                canonical_nodes.append(author_node)
                            
                            final_relationships.append({
                                "from": title,
                                "to": author,
                                "type": "AUTHORED_BY"
                            })
            except Exception as e:
                logger.error(f"Failed to extract citations from bibliography: {e}")

        # Ensure main document is connected to the graph if it has no citations
        concept_candidates = [
            n for n in canonical_nodes
            if n is not paper_node and n.get("label") in ["Topic", "Concept", "Method", "Dataset"]
        ]
        if concept_candidates:
            anchor = max(
                concept_candidates,
                key=lambda n: len(adj.get(n.get("name", "").lower().strip(), set()))
            )
            final_relationships.append({
                "from": paper_node["name"],
                "to": anchor["name"],
                "type": "MENTIONS"
            })
            paper_key = paper_node["name"].lower().strip()
            anchor_key = anchor["name"].lower().strip()
            adj.setdefault(paper_key, set()).add(anchor_key)
            adj.setdefault(anchor_key, set()).add(paper_key)

        # Infer hierarchy levels after merging so the visual graph can lay out as:
        # prerequisites above -> core topic center -> advanced/application nodes below.
        node_by_name = {n.get("name", "").lower().strip(): n for n in canonical_nodes if n.get("name")}
        central_key = resolved_central_name.lower().strip()
        if central_key in node_by_name:
            node_by_name[central_key]["level"] = "core"
        for rel in final_relationships:
            f_key = rel.get("from", "").lower().strip()
            t_key = rel.get("to", "").lower().strip()
            r_type = rel.get("type", "").upper()
            if r_type in ["PREREQUISITE", "PREREQUISITE_OF"]:
                if f_key in node_by_name:
                    node_by_name[f_key]["level"] = "foundation"
                if t_key in node_by_name and not node_by_name[t_key].get("level"):
                    node_by_name[t_key]["level"] = "core"
            elif r_type == "EXTENDS":
                if f_key in node_by_name and not node_by_name[f_key].get("level"):
                    node_by_name[f_key]["level"] = "core"
                if t_key in node_by_name:
                    node_by_name[t_key]["level"] = "advanced"
            elif r_type in ["USED_FOR", "EVALUATED_ON", "CITES", "AUTHORED_BY"]:
                if t_key in node_by_name and not node_by_name[t_key].get("level"):
                    node_by_name[t_key]["level"] = "advanced"
        for n in canonical_nodes:
            n.setdefault("level", "advanced" if n.get("label") in ["Paper", "Author", "Dataset"] else "core")

        # Log top extracted concepts and relationships
        logger.info("=== TOP EXTRACTED KNOWLEDGE GRAPH ELEMENTS ===")
        sorted_nodes_log = sorted(canonical_nodes, key=lambda x: len(adj.get(x["name"].lower().strip(), set())), reverse=True)
        logger.info("Top 10 Concepts (sorted by connections):")
        for node in sorted_nodes_log[:10]:
            deg = len(adj.get(node["name"].lower().strip(), set()))
            logger.info(f"  - [{node.get('label')}] {node.get('name')} ({deg} connections): {node.get('description')[:120]}...")
            
        logger.info("Top 10 Relationships:")
        for rel in final_relationships[:10]:
            logger.info(f"  - {rel.get('from')} --[{rel.get('type')}]--> {rel.get('to')}")
            
        logger.info(f"Writing {len(canonical_nodes)} canonical nodes and {len(final_relationships)} connected relationships to Neo4j.")
        try:
            first_embedding = next((n.get("embedding") for n in canonical_nodes if n.get("embedding")), None)
            if first_embedding and not neo4j_client.is_mock():
                neo4j_client.run_query(
                    f"""
                    CREATE VECTOR INDEX concept_embedding IF NOT EXISTS
                    FOR (n:Concept) ON (n.embedding)
                    OPTIONS {{indexConfig: {{
                        `vector.dimensions`: {len(first_embedding)},
                        `vector.similarity_function`: 'cosine'
                    }}}}
                    """,
                    {}
                )
        except Exception as e:
            logger.warning(f"Could not ensure Neo4j concept embedding index: {e}")
        
        # Write nodes to Neo4j
        for node in canonical_nodes:
            label = node.get("label", "Concept")
            if label not in ["Topic", "Subtopic", "Concept", "Technology", "Framework", "Application", "Paper", "Author", "Keyword", "Method", "Dataset"]:
                label = "Concept"
            name = node.get("name").strip()
            desc = node.get("description", "").strip()
            
            node_id = str(uuid.uuid4())
            
            # Check multi-document mode config
            multi_doc_mode = getattr(config, "MULTI_DOCUMENT_MODE", False) or (session_id is not None)

            # Neo4j query
            if label == "Paper":
                year = node.get("year")
                venue = node.get("venue")
                doi = node.get("doi")
                if session_id:
                    query = """
                    MERGE (n:Paper {name: $name, session_id: $session_id})
                    ON CREATE SET n.id = $id, n.title = $name, n.description = $description, n.difficulty_level = 'Beginner', n.doc_id = $doc_id, n.year = $year, n.venue = $venue, n.doi = $doi, n.embedding = $embedding
                    ON MATCH SET n.title = $name, n.description = CASE WHEN n.description IS NULL OR n.description = '' THEN $description ELSE n.description END, n.year = $year, n.venue = $venue, n.doi = $doi, n.embedding = coalesce(n.embedding, $embedding)
                    RETURN n.id as node_id
                    """
                elif multi_doc_mode:
                    query = """
                    MERGE (n:Paper {name: $name})
                    ON CREATE SET n.id = $id, n.title = $name, n.description = $description, n.difficulty_level = 'Beginner', n.doc_id = $doc_id, n.year = $year, n.venue = $venue, n.doi = $doi, n.embedding = $embedding
                    ON MATCH SET n.title = $name, n.description = CASE WHEN n.description IS NULL OR n.description = '' THEN $description ELSE n.description END, n.year = $year, n.venue = $venue, n.doi = $doi, n.embedding = coalesce(n.embedding, $embedding)
                    RETURN n.id as node_id
                    """
                else:
                    query = """
                    MERGE (n:Paper {name: $name, doc_id: $doc_id})
                    ON CREATE SET n.id = $id, n.title = $name, n.description = $description, n.difficulty_level = 'Beginner', n.year = $year, n.venue = $venue, n.doi = $doi, n.embedding = $embedding
                    ON MATCH SET n.title = $name, n.description = CASE WHEN n.description IS NULL OR n.description = '' THEN $description ELSE n.description END, n.year = $year, n.venue = $venue, n.doi = $doi, n.embedding = coalesce(n.embedding, $embedding)
                    RETURN n.id as node_id
                    """
            else:
                if session_id:
                    query = f"""
                    MERGE (n:Concept {{name: $name, session_id: $session_id}})
                    SET n:{label}
                    ON CREATE SET n.id = $id, n.description = $description, n.difficulty_level = 'Beginner', n.doc_id = $doc_id, n.embedding = $embedding
                    ON MATCH SET n.description = CASE WHEN n.description IS NULL OR n.description = '' THEN $description ELSE n.description END, n.embedding = coalesce(n.embedding, $embedding)
                    RETURN n.id as node_id
                    """
                elif multi_doc_mode:
                    query = f"""
                    MERGE (n:Concept {{name: $name}})
                    SET n:{label}
                    ON CREATE SET n.id = $id, n.description = $description, n.difficulty_level = 'Beginner', n.doc_id = $doc_id, n.embedding = $embedding
                    ON MATCH SET n.description = CASE WHEN n.description IS NULL OR n.description = '' THEN $description ELSE n.description END, n.embedding = coalesce(n.embedding, $embedding)
                    RETURN n.id as node_id
                    """
                else:
                    query = f"""
                    MERGE (n:Concept {{name: $name, doc_id: $doc_id}})
                    SET n:{label}
                    ON CREATE SET n.id = $id, n.description = $description, n.difficulty_level = 'Beginner', n.embedding = $embedding
                    ON MATCH SET n.description = CASE WHEN n.description IS NULL OR n.description = '' THEN $description ELSE n.description END, n.embedding = coalesce(n.embedding, $embedding)
                    RETURN n.id as node_id
                    """
            
            res = neo4j_client.run_query(query, {
                "name": name, 
                "id": node_id, 
                "description": desc, 
                "doc_id": doc_id,
                "session_id": session_id,
                "year": node.get("year"),
                "venue": node.get("venue"),
                "doi": node.get("doi"),
                "embedding": node.get("embedding") or embedding_client.embed_node(node)
            })
            
            # Capture the resolved node ID
            resolved_id = node_id
            if res and res[0].get("node_id"):
                resolved_id = res[0]["node_id"]
            node["resolved_id"] = resolved_id
            
            # Link node to Document (using label-agnostic MATCH to avoid mismatch)
            link_query = f"""
            MATCH (d:Document {{id: $doc_id}})
            MATCH (n {{id: $node_id}})
            MERGE (d)-[:CONTAINS]->(n)
            """
            neo4j_client.run_query(link_query, {"doc_id": doc_id, "node_id": resolved_id})

            # Also seed to mock store if in mock mode
            if neo4j_client.is_mock():
                existing_id = None
                for nid, mn in neo4j_client.mock_nodes.items():
                    mn_label = mn.get("label", "Concept")
                    is_label_match = (
                        (label in ["Concept", "Topic", "Subtopic", "Keyword", "Author", "Method", "Dataset", "Technology", "Framework", "Application"] and mn_label in ["Concept", "Topic", "Subtopic", "Keyword", "Author", "Method", "Dataset", "Technology", "Framework", "Application"])
                        or label == mn_label
                    )
                    if is_label_match and mn.get("name", "").lower() == name.lower():
                        if mn.get("session_id") == session_id:
                            existing_id = nid
                            break
                if existing_id:
                    resolved_id = existing_id
                    if not neo4j_client.mock_nodes[resolved_id].get("description"):
                        neo4j_client.mock_nodes[resolved_id]["description"] = desc
                    if node.get("level"):
                        neo4j_client.mock_nodes[resolved_id]["level"] = node["level"]
                    if node.get("embedding"):
                        neo4j_client.mock_nodes[resolved_id]["embedding"] = node["embedding"]
                else:
                    resolved_id = node_id
                    node_data = {
                        "id": resolved_id,
                        "label": label,
                        "name": name,
                        "description": desc,
                        "difficulty_level": "Beginner",
                        "doc_id": doc_id,
                        "session_id": session_id,
                        "embedding": node.get("embedding") or embedding_client.embed_node(node)
                    }
                    if node.get("level"):
                        node_data["level"] = node["level"]
                    if label == "Paper":
                        node_data["title"] = name
                        if "year" in node:
                            node_data["year"] = node["year"]
                        if "doi" in node:
                            node_data["doi"] = node["doi"]
                    neo4j_client.mock_nodes[resolved_id] = node_data
                node["resolved_id"] = resolved_id

        # Write relationships to Neo4j
        for rel in final_relationships:
            from_name = rel.get("from")
            to_name = rel.get("to")
            rel_type = rel.get("type", "RELATED_TO").strip()
            
            if not from_name or not to_name:
                continue
                
            if rel_type not in ["PREREQUISITE", "PREREQUISITE_OF", "RELATED_TO", "EXTENDS", "CONTRADICTS", "USES", "USES_METHOD", "DEPENDS_ON", "USED_BY", "PART_OF", "CAUSES", "CITES", "AUTHORED_BY", "AFFILIATED_WITH", "MENTIONS", "HAS_KEYWORD", "USED_FOR", "EVALUATED_ON"]:
                rel_type = "RELATED_TO"
                
            if session_id:
                query = f"""
                MATCH (a {{name: $from_name, session_id: $session_id}})
                MATCH (b {{name: $to_name, session_id: $session_id}})
                MERGE (a)-[r:{rel_type}]->(b)
                ON CREATE SET r.session_id = $session_id, r.doc_id = $doc_id, r.doc_ids = [$doc_id]
                ON MATCH SET r.session_id = $session_id,
                             r.doc_id = coalesce(r.doc_id, $doc_id),
                             r.doc_ids = CASE
                               WHEN $doc_id IN coalesce(r.doc_ids, []) THEN r.doc_ids
                               ELSE coalesce(r.doc_ids, []) + $doc_id
                             END
                """
                neo4j_client.run_query(query, {"from_name": from_name, "to_name": to_name, "session_id": session_id, "doc_id": doc_id})
            else:
                query = f"""
                MATCH (a {{name: $from_name, doc_id: $doc_id}})
                MATCH (b {{name: $to_name, doc_id: $doc_id}})
                MERGE (a)-[r:{rel_type}]->(b)
                ON CREATE SET r.doc_id = $doc_id, r.doc_ids = [$doc_id]
                ON MATCH SET r.doc_id = coalesce(r.doc_id, $doc_id),
                             r.doc_ids = CASE
                               WHEN $doc_id IN coalesce(r.doc_ids, []) THEN r.doc_ids
                               ELSE coalesce(r.doc_ids, []) + $doc_id
                             END
                """
                neo4j_client.run_query(query, {"from_name": from_name, "to_name": to_name, "doc_id": doc_id})
            
            # Also seed to mock store if in mock mode
            if neo4j_client.is_mock():
                # Find matched nodes in mock for this document/session namespace
                from_id = None
                to_id = None
                for nid, n in neo4j_client.mock_nodes.items():
                    if n.get("name", "").lower() == from_name.lower():
                        if (session_id and n.get("session_id") == session_id) or (not session_id and (multi_doc_mode or n.get("doc_id") == doc_id)):
                            from_id = nid
                    if n.get("name", "").lower() == to_name.lower():
                        if (session_id and n.get("session_id") == session_id) or (not session_id and (multi_doc_mode or n.get("doc_id") == doc_id)):
                            to_id = nid
                if from_id and to_id:
                    neo4j_client.mock_edges.append({
                        "from": from_id,
                        "to": to_id,
                        "type": rel_type,
                        "doc_id": doc_id,
                        "session_id": session_id
                    })
                    
        # Update status to done
        _persist_mock_session_graph(session_id)
        _save_doc_status(
            doc_id,
            "done",
            100,
            None,
            session_id,
            failed_chunks=failed_chunks,
            total_chunks=total_chunks,
            extraction_mode="full_document_chunked",
            ocr_used=bool(text_meta.get("ocr_used")),
            ocr_confidence=text_meta.get("ocr_confidence"),
        )
        _save_session_doc(session_id, {
            "id": doc_id,
            "title": filename,
            "status": "done",
            "progress_pct": 100,
        })
        
        # Save completed status to Neo4j node
        neo4j_client.run_query(
            """
            MATCH (d:Document {id: $doc_id})
            SET d.status = 'done',
                d.progress_pct = 100,
                d.failed_chunks = $failed_chunks,
                d.total_chunks = $total_chunks,
                d.extraction_mode = 'full_document_chunked',
                d.ocr_used = $ocr_used,
                d.ocr_confidence = $ocr_confidence
            """,
            {
                "doc_id": doc_id,
                "failed_chunks": failed_chunks,
                "total_chunks": total_chunks,
                "ocr_used": bool(text_meta.get("ocr_used")),
                "ocr_confidence": text_meta.get("ocr_confidence"),
            }
        )
        logger.info(f"Extraction pipeline completed successfully for document {doc_id}.")
        
    except Exception as e:
        logger.error(f"Extraction failed for document {doc_id}: {e}")
        error_msg = str(e)
        _persist_mock_session_graph(session_id)
        _save_doc_status(
            doc_id,
            "error",
            100,
            error_msg,
            session_id,
            failed_chunks=failed_chunks,
            total_chunks=total_chunks,
            extraction_mode="full_document_chunked",
            ocr_used=bool(text_meta.get("ocr_used")),
            ocr_confidence=text_meta.get("ocr_confidence"),
        )
        _save_session_doc(session_id, {
            "id": doc_id,
            "title": filename,
            "status": "error",
            "progress_pct": 100,
        })
        
        # Clean up any partial nodes or relationships created during this failed run to prevent contamination
        try:
            if neo4j_client.is_mock():
                nodes_to_delete = {nid for nid, n in neo4j_client.mock_nodes.items() if n.get("doc_id") == doc_id}
                for nid in nodes_to_delete:
                    neo4j_client.mock_nodes.pop(nid, None)
                neo4j_client.mock_edges = [
                    e for e in neo4j_client.mock_edges 
                    if e.get("doc_id") != doc_id
                ]
            else:
                neo4j_client.run_query(
                    "MATCH (n) WHERE n.doc_id = $doc_id DETACH DELETE n",
                    {"doc_id": doc_id}
                )
        except Exception as cleanup_err:
            logger.error(f"Failed to clean up contaminated nodes/edges for failed doc {doc_id}: {cleanup_err}")

        neo4j_client.run_query(
            """
            MATCH (d:Document {id: $doc_id})
            SET d.status = 'error',
                d.error_msg = $error,
                d.failed_chunks = $failed_chunks,
                d.total_chunks = $total_chunks,
                d.extraction_mode = 'full_document_chunked',
                d.ocr_used = $ocr_used,
                d.ocr_confidence = $ocr_confidence
            """,
            {
                "doc_id": doc_id,
                "error": error_msg,
                "failed_chunks": failed_chunks,
                "total_chunks": total_chunks,
                "ocr_used": bool(text_meta.get("ocr_used")),
                "ocr_confidence": text_meta.get("ocr_confidence"),
            }
        )
def delete_document_internal(doc_id: str, session_id: Optional[str] = None):
    import os
    import re
    # Fetch Document storage URL
    if neo4j_client.is_mock():
        doc = neo4j_client.mock_nodes.get(doc_id)
        if not doc or doc.get("label") != "Document":
            raise HTTPException(status_code=404, detail="Document not found.")
        if session_id and doc.get("session_id") != session_id:
            raise HTTPException(status_code=403, detail="Access denied. Document does not belong to this session.")
        url = doc.get("storage_url", "")
    else:
        query = "MATCH (d:Document {id: $doc_id}) RETURN d.storage_url as url, d.session_id as session_id"
        res = neo4j_client.run_query(query, {"doc_id": doc_id})
        if not res:
            raise HTTPException(status_code=404, detail="Document not found.")
        record = res[0]
        if session_id and record.get("session_id") != session_id:
            raise HTTPException(status_code=403, detail="Access denied. Document does not belong to this session.")
        url = record.get("url") or record.get("storage_url") or ""

    # Delete storage file
    if url:
        blob_path = _blob_path_from_storage_url(url)
        if blob_path and vercel_blob_client.is_configured():
            vercel_blob_client.delete(blob_path)
        elif url.startswith("file:///"):
            filename = os.path.basename(url)
            supabase_client.delete_file("documents", filename)
        else:
            match = re.search(r'documents/(uploads/.*)', url)
            if match:
                path = match.group(1)
                supabase_client.delete_file("documents", path)

    # Delete nodes & edges
    if neo4j_client.is_mock():
        # Pop highlight nodes linked to this doc in mock
        highlight_ids = {
            e["from"] for e in neo4j_client.mock_edges 
            if e["to"] == doc_id and e["type"] == "EXTRACTED_FROM"
        }
        for hid in highlight_ids:
            neo4j_client.mock_nodes.pop(hid, None)
            
        # Pop citation nodes linked to papers of this doc in mock
        paper_ids = {
            nid for nid, n in neo4j_client.mock_nodes.items() 
            if n.get("doc_id") == doc_id and n.get("label") == "Paper"
        }
        citation_ids = {
            e["from"] for e in neo4j_client.mock_edges 
            if e["to"] in paper_ids and e["type"] == "FOR_PAPER"
        }
        for cid in citation_ids:
            neo4j_client.mock_nodes.pop(cid, None)

        # Pop doc node and this document's own edges. Keep shared concept nodes
        # if any surviving edge from another document still references them.
        neo4j_client.mock_nodes.pop(doc_id, None)
        candidate_node_ids = {nid for nid, n in neo4j_client.mock_nodes.items() if n.get("doc_id") == doc_id}
        deleted_ids = {doc_id} | highlight_ids | citation_ids
        neo4j_client.mock_edges = [
            e for e in neo4j_client.mock_edges
            if e.get("doc_id") != doc_id and e.get("from") not in deleted_ids and e.get("to") not in deleted_ids
        ]
        still_referenced = set()
        for e in neo4j_client.mock_edges:
            still_referenced.add(e.get("from"))
            still_referenced.add(e.get("to"))
        for nid in candidate_node_ids:
            if nid not in still_referenced:
                neo4j_client.mock_nodes.pop(nid, None)
        # Pop from status cache
        extraction_status_cache.pop(doc_id, None)
    else:
        # 1. Delete highlights linked to this document
        neo4j_client.run_query("MATCH (h:Highlight)-[:EXTRACTED_FROM]->(d:Document {id: $doc_id}) DETACH DELETE h", {"doc_id": doc_id})
        # 2. Delete citations linked to papers of this document
        neo4j_client.run_query("MATCH (c:Citation)-[:FOR_PAPER]->(p:Paper {doc_id: $doc_id}) DETACH DELETE c", {"doc_id": doc_id})
        # 3. Delete this document's contribution without deleting concepts also linked to other documents.
        neo4j_client.run_query(
            """
            MATCH ()-[r]->()
            WHERE $doc_id IN coalesce(r.doc_ids, [])
            SET r.doc_ids = [x IN r.doc_ids WHERE x <> $doc_id]
            """,
            {"doc_id": doc_id}
        )
        neo4j_client.run_query(
            """
            MATCH ()-[r]->()
            WHERE r.doc_id = $doc_id AND (r.doc_ids IS NULL OR size(r.doc_ids) = 0)
            DELETE r
            """,
            {"doc_id": doc_id}
        )
        neo4j_client.run_query(
            """
            MATCH (d:Document {id: $doc_id})-[r:CONTAINS]->(n)
            DELETE r
            WITH collect(n) AS touched
            UNWIND touched AS n
            WITH n
            WHERE NOT ( (:Document)-[:CONTAINS]->(n) )
            DETACH DELETE n
            """,
            {"doc_id": doc_id}
        )
        neo4j_client.run_query("MATCH (d:Document {id: $doc_id}) DETACH DELETE d", {"doc_id": doc_id})
        extraction_status_cache.pop(doc_id, None)

def _process_file_upload(
    file_bytes: bytes,
    filename: str,
    session_id: Optional[str],
    replace_doc_id: Optional[str],
    background_tasks: BackgroundTasks
) -> UploadResponse:
    """Common file upload processing logic shared by direct and chunked uploads."""
    try:
        # Delete document to be replaced if specified
        if replace_doc_id:
            delete_document_internal(replace_doc_id, session_id)

        # Generate unique document ID
        doc_id = str(uuid.uuid4())
        path = f"uploads/{doc_id}_{filename}"

        # Upload to durable storage. On Vercel, Blob is available and serverless-safe;
        # Supabase remains the fallback for local/dev deployments configured with it.
        if vercel_blob_client.is_configured():
            blob_result = vercel_blob_client.put(path, file_bytes, "application/pdf")
            storage_url = blob_result.get("url") or f"vercel-blob://{path}"
        else:
            storage_url = supabase_client.upload_file("documents", path, file_bytes)

        # Write Document node to Neo4j
        upload_date = datetime.datetime.now().isoformat()
        query = """
        MERGE (d:Document {id: $id})
        ON CREATE SET d.title = $title, d.type = 'pdf', d.upload_date = $upload_date, 
                      d.storage_url = $storage_url, d.status = 'processing', d.progress_pct = 10,
                      d.session_id = $session_id, d.failed_chunks = 0, d.total_chunks = 0,
                      d.extraction_mode = 'full_document_chunked', d.ocr_used = false
        RETURN d
        """
        neo4j_client.run_query(query, {
            "id": doc_id,
            "title": filename,
            "upload_date": upload_date,
            "storage_url": storage_url,
            "session_id": session_id
        })

        # Also seed Document to mock store if in mock mode
        if neo4j_client.is_mock():
            neo4j_client.mock_nodes[doc_id] = {
                "id": doc_id,
                "label": "Document",
                "title": filename,
                "type": "pdf",
                "status": "processing",
                "progress_pct": 10,
                "upload_date": upload_date,
                "storage_url": storage_url,
                "session_id": session_id
            }

        # Set initial status/doc list in durable state as well as local cache.
        _save_doc_status(doc_id, "processing", 10, None, session_id)
        _save_session_doc(session_id, {
            "id": doc_id,
            "title": filename,
            "status": "processing",
            "progress_pct": 10,
        })

        # Trigger background task
        background_tasks.add_task(run_extraction_pipeline, doc_id, file_bytes, filename, session_id)

        return UploadResponse(id=doc_id, status="processing", title=filename)
    except Exception as e:
        logger.error(f"Failed to process file upload: {e}")
        raise


class StartChunkedUploadResponse(BaseModel):
    upload_id: str
    total_chunks: int
    chunk_size: int


class ChunkUploadResponse(BaseModel):
    chunk_index: int
    received: int
    total: int
    complete: bool


@router.post("/documents/start-chunked-upload")
async def start_chunked_upload(
    filename: str = Query(...),
    total_chunks: int = Query(...),
    file_size: int = Query(...),
    session_id: Optional[str] = Query(None),
    replace_doc_id: Optional[str] = Query(None)
):
    if not filename.endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF documents are supported.")

    # Clean up any orphaned upload sessions older than MAX_CHUNK_AGE_SECONDS
    now = datetime.datetime.now().timestamp()
    stale_ids = [
        uid for uid, session in chunked_uploads.items()
        if now - session.get("created_at", 0) > MAX_CHUNK_AGE_SECONDS
    ]
    for stale_id in stale_ids:
        logger.info(f"Cleaning up stale chunked upload session {stale_id}")
        del chunked_uploads[stale_id]

    upload_id = str(uuid.uuid4())
    chunked_uploads[upload_id] = {
        "chunks": {},
        "total": total_chunks,
        "filename": filename,
        "file_size": file_size,
        "session_id": session_id,
        "replace_doc_id": replace_doc_id,
        "created_at": now
    }
    try:
        _save_chunk_session(upload_id, chunked_uploads[upload_id])
    except Exception as e:
        logger.error(f"Failed to persist chunked upload session {upload_id}: {e}")
        chunked_uploads.pop(upload_id, None)
        raise HTTPException(status_code=500, detail="Failed to initialize persistent upload session.")
    logger.info(f"Started chunked upload {upload_id} for {filename} ({total_chunks} chunks, {file_size} bytes)")
    return StartChunkedUploadResponse(
        upload_id=upload_id,
        total_chunks=total_chunks,
        chunk_size=CHUNK_SIZE
    )


@router.post("/documents/upload-chunk")
async def upload_chunk(
    upload_id: str = Query(...),
    chunk_index: int = Query(...),
    file: UploadFile = File(...)
):
    upload = _load_chunk_session(upload_id)
    if not upload:
        raise HTTPException(status_code=404, detail="Upload session not found. Please start a new upload.")

    chunk_data = await file.read()
    if chunk_index < 0 or chunk_index >= int(upload["total"]):
        raise HTTPException(status_code=400, detail="Chunk index out of range.")

    try:
        if vercel_blob_client.is_configured():
            vercel_blob_client.put(_chunk_part_path(upload_id, chunk_index), chunk_data, "application/octet-stream")
        else:
            supabase_client.upload_file(
                "documents",
                _chunk_part_path(upload_id, chunk_index),
                chunk_data,
                content_type="application/octet-stream",
            )
    except Exception as e:
        logger.error(f"Failed to persist chunk {chunk_index} for upload {upload_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to store upload chunk.")

    upload.setdefault("chunks", {})[chunk_index] = True
    received = len(upload["chunks"])
    total = int(upload["total"])

    logger.info(f"Received chunk {chunk_index + 1}/{total} for upload {upload_id}")

    return ChunkUploadResponse(
        chunk_index=chunk_index,
        received=received,
        total=total,
        complete=received >= total
    )


@router.post("/documents/complete-chunked-upload", response_model=UploadResponse)
async def complete_chunked_upload(
    upload_id: str = Query(...),
    background_tasks: BackgroundTasks = BackgroundTasks()
):
    upload = _load_chunk_session(upload_id)
    if not upload:
        raise HTTPException(status_code=404, detail="Upload session not found.")

    total_chunks = int(upload["total"])
    chunks: list[bytes] = []
    missing: list[int] = []

    for i in range(total_chunks):
        try:
            if vercel_blob_client.is_configured():
                chunks.append(vercel_blob_client.get(_chunk_part_path(upload_id, i)))
            else:
                chunks.append(supabase_client.download_file("documents", _chunk_part_path(upload_id, i)))
        except Exception:
            missing.append(i)

    if missing:
        raise HTTPException(status_code=400, detail=f"Missing {len(missing)} chunks. Complete upload first.")

    # Reassemble file from persistent chunks
    file_bytes = b"".join(chunks)

    # Clean up the persistent upload session
    _delete_chunk_session(upload_id, total_chunks)

    # Process using the shared helper
    return _process_file_upload(
        file_bytes,
        upload["filename"],
        upload["session_id"],
        upload.get("replace_doc_id"),
        background_tasks
    )


@router.post("/documents/upload", response_model=UploadResponse)
async def upload_document(
    background_tasks: BackgroundTasks, 
    file: UploadFile = File(...),
    session_id: Optional[str] = Query(None),
    replace_doc_id: Optional[str] = Query(None)
):
    if not file.filename.endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF documents are supported.")
        
    # Sanitize query parameters if called directly in tests as dependency parameters
    if not isinstance(session_id, str):
        session_id = None
    if not isinstance(replace_doc_id, str):
        replace_doc_id = None
        
    try:
        file_bytes = await file.read()
        return _process_file_upload(file_bytes, file.filename, session_id, replace_doc_id, background_tasks)
    except Exception as e:
        logger.error(f"Failed to upload document: {e}")
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")

@router.get("/documents/{id}/status", response_model=StatusResponse)
def get_document_status(id: str, session_id: Optional[str] = Query(None)):
    if not isinstance(session_id, str):
        session_id = None
    # Validate session ownership if session_id is provided
    if session_id:
        if neo4j_client.is_mock():
            doc = neo4j_client.mock_nodes.get(id)
            if doc and doc.get("session_id") != session_id:
                raise HTTPException(status_code=403, detail="Access denied. Document does not belong to this session.")
        else:
            query = "MATCH (d:Document {id: $id}) RETURN d.session_id as session_id"
            res = neo4j_client.run_query(query, {"id": id})
            if res and res[0].get("session_id") != session_id:
                raise HTTPException(status_code=403, detail="Access denied. Document does not belong to this session.")

    # Check cache first
    status = extraction_status_cache.get(id)
    if status:
        return StatusResponse(**status)

    persisted_status = _load_json_state("doc-status", id)
    if persisted_status:
        if session_id and persisted_status.get("session_id") != session_id:
            raise HTTPException(status_code=403, detail="Access denied. Document does not belong to this session.")
        return StatusResponse(
            status=persisted_status.get("status") or "processing",
            progress_pct=persisted_status.get("progress_pct") or 10,
            error=persisted_status.get("error"),
            failed_chunks=persisted_status.get("failed_chunks") or 0,
            total_chunks=persisted_status.get("total_chunks") or 0,
            extraction_mode=persisted_status.get("extraction_mode"),
            ocr_used=bool(persisted_status.get("ocr_used")),
            ocr_confidence=persisted_status.get("ocr_confidence"),
        )
        
    # Check database next
    query = """
    MATCH (d:Document {id: $id})
    RETURN d.status as status,
           d.progress_pct as progress_pct,
           d.error_msg as error_msg,
           d.failed_chunks as failed_chunks,
           d.total_chunks as total_chunks,
           d.extraction_mode as extraction_mode,
           d.ocr_used as ocr_used,
           d.ocr_confidence as ocr_confidence
    """
    res = neo4j_client.run_query(query, {"id": id})
    if res:
        record = res[0]
        return StatusResponse(
            status=record.get("status") or "processing",
            progress_pct=record.get("progress_pct") or 10,
            error=record.get("error_msg"),
            failed_chunks=record.get("failed_chunks") or 0,
            total_chunks=record.get("total_chunks") or 0,
            extraction_mode=record.get("extraction_mode"),
            ocr_used=bool(record.get("ocr_used")),
            ocr_confidence=record.get("ocr_confidence"),
        )
        
    raise HTTPException(status_code=404, detail="Document not found.")

@router.get("/documents/{id}/graph")
def get_document_graph(id: str, session_id: Optional[str] = Query(None)):
    if not isinstance(session_id, str):
        session_id = None
    # Validate session ownership if session_id is provided
    if session_id:
        if neo4j_client.is_mock():
            doc = neo4j_client.mock_nodes.get(id)
            if doc and doc.get("session_id") != session_id:
                raise HTTPException(status_code=403, detail="Access denied. Document does not belong to this session.")
        else:
            query = "MATCH (d:Document {id: $id}) RETURN d.session_id as session_id"
            res = neo4j_client.run_query(query, {"id": id})
            if res and res[0].get("session_id") != session_id:
                raise HTTPException(status_code=403, detail="Access denied. Document does not belong to this session.")

    multi_doc_mode = getattr(config, "MULTI_DOCUMENT_MODE", False)

    if neo4j_client.is_mock():
        if not neo4j_client.mock_nodes:
            persisted_status = _load_json_state("doc-status", id)
            persisted_graph = _load_json_state("session-graph", persisted_status.get("session_id")) if persisted_status else None
            if persisted_graph:
                nodes = [_public_node(n) for n in persisted_graph.get("nodes", []) if n.get("doc_id") == id]
                node_ids = {n.get("id") for n in nodes}
                edges = [
                    e for e in persisted_graph.get("edges", [])
                    if e.get("doc_id") == id or (e.get("from") in node_ids and e.get("to") in node_ids)
                ]
                return {"nodes": nodes, "edges": edges}

        # Find all mock nodes containing relationships with this document ID
        doc_node_ids = set()
        for edge in neo4j_client.mock_edges:
            if edge["from"] == id and edge["type"] == "CONTAINS":
                doc_node_ids.add(edge["to"])
        
        # If the document is the initial placeholder "doc-1" and has no CONTAINS relationships,
        # fallback to returning all pre-seeded ML concepts (excluding the Document node itself)
        if not doc_node_ids and id == "doc-1":
            ml_nodes = []
            for n in neo4j_client.mock_nodes.values():
                if n.get("label") != "Document":
                    ml_nodes.append(_public_node(n))
            ml_node_ids = {n["id"] for n in ml_nodes}
            ml_edges = [
                e for e in neo4j_client.mock_edges 
                if e["type"] != "CONTAINS" and e["from"] in ml_node_ids and e["to"] in ml_node_ids
            ]
            return {"nodes": ml_nodes, "edges": ml_edges}
            
        # Return only the nodes and edges for this specific document
        doc_nodes = []
        for nid, n in neo4j_client.mock_nodes.items():
            if nid in doc_node_ids:
                node_doc_id = n.get("doc_id")
                # Validation: if not multi-document mode, verify node matches document namespace
                if not multi_doc_mode and node_doc_id and node_doc_id != id:
                    logger.error(f"Validation Error: Node {n.get('name') or n.get('title')} belongs to document {node_doc_id}, expected {id}")
                    continue
                doc_nodes.append(_public_node(n))
                
        doc_edges = [
            e for e in neo4j_client.mock_edges 
            if e["type"] != "CONTAINS" and e.get("doc_id") == id
        ]
        return {"nodes": doc_nodes, "edges": doc_edges}
        
    # Fetch nodes in the document
    nodes_query = """
    MATCH (d:Document {id: $doc_id})-[:CONTAINS]->(n)
    RETURN labels(n)[0] as label, n.id as id, coalesce(n.name, n.title) as name, n.description as description, n.difficulty_level as difficulty_level, n.doc_id as doc_id, n.year as year, n.doi as doi
    """
    nodes_res = neo4j_client.run_query(nodes_query, {"doc_id": id})
    
    # Fetch edges between nodes in the document
    edges_query = """
    MATCH (d:Document {id: $doc_id})-[:CONTAINS]->(n)
    MATCH (d)-[:CONTAINS]->(m)
    MATCH (n)-[r]->(m)
    WHERE r.doc_id = $doc_id
    RETURN n.id as from_id, m.id as to_id, type(r) as type
    """
    edges_res = neo4j_client.run_query(edges_query, {"doc_id": id})
    
    nodes = []
    valid_node_ids = set()
    for r in nodes_res:
        node_doc_id = r.get("doc_id")
        # Validation: if not multi-document mode, verify node matches document namespace
        if not multi_doc_mode and node_doc_id and node_doc_id != id:
            logger.error(f"Validation Error: Node {r['name']} belongs to document {node_doc_id}, expected {id}")
            continue
        node_data = {
            "id": r["id"],
            "label": r["label"],
            "name": r["name"] or "Unknown",
            "description": r.get("description", ""),
            "difficulty_level": r.get("difficulty_level", "Beginner"),
            "doc_id": node_doc_id
        }
        if r.get("year") is not None:
            node_data["year"] = r["year"]
        if r.get("doi") is not None:
            node_data["doi"] = r["doi"]
        nodes.append(node_data)
        valid_node_ids.add(r["id"])
        
    edges = []
    for r in edges_res:
        if r["from_id"] in valid_node_ids and r["to_id"] in valid_node_ids:
            edges.append({
                "from": r["from_id"],
                "to": r["to_id"],
                "type": r["type"]
            })
        
    return {"nodes": nodes, "edges": edges}

@router.get("/sessions/{session_id}/graph")
def get_session_graph(session_id: str):
    if neo4j_client.is_mock():
        session_nodes = []
        session_node_ids = set()
        for nid, n in neo4j_client.mock_nodes.items():
            if n.get("session_id") == session_id and n.get("label") not in ["Document", "Note", "Highlight", "Citation"]:
                session_nodes.append(_public_node(n))
                session_node_ids.add(nid)
            
        session_edges = [
            e for e in neo4j_client.mock_edges 
            if e["type"] != "CONTAINS" and e.get("session_id") == session_id
        ]
        if not session_nodes and not session_edges:
            persisted_graph = _load_json_state("session-graph", session_id)
            if persisted_graph:
                return {
                    "nodes": [_public_node(n) for n in persisted_graph.get("nodes", [])],
                    "edges": persisted_graph.get("edges", [])
                }
        return {"nodes": session_nodes, "edges": session_edges}

    # Real Neo4j Mode
    nodes_query = """
    MATCH (n)
    WHERE n.session_id = $session_id AND NOT n:Document AND NOT n:Note AND NOT n:Highlight AND NOT n:Citation
    RETURN labels(n)[0] as label, n.id as id, coalesce(n.name, n.title) as name, n.description as description, n.difficulty_level as difficulty_level, n.doc_id as doc_id, n.year as year, n.doi as doi
    """
    nodes_res = neo4j_client.run_query(nodes_query, {"session_id": session_id})
    
    edges_query = """
    MATCH (n) WHERE n.session_id = $session_id AND NOT n:Document AND NOT n:Note AND NOT n:Highlight AND NOT n:Citation
    MATCH (m) WHERE m.session_id = $session_id AND NOT m:Document AND NOT m:Note AND NOT m:Highlight AND NOT m:Citation
    MATCH (n)-[r]->(m)
    WHERE r.session_id = $session_id
    RETURN n.id as from_id, m.id as to_id, type(r) as type
    """
    edges_res = neo4j_client.run_query(edges_query, {"session_id": session_id})
    
    nodes = []
    valid_node_ids = set()
    for r in nodes_res:
        node_data = {
            "id": r["id"],
            "label": r["label"],
            "name": r["name"] or "Unknown",
            "description": r.get("description", ""),
            "difficulty_level": r.get("difficulty_level", "Beginner"),
            "doc_id": r.get("doc_id")
        }
        if r.get("year") is not None:
            node_data["year"] = r["year"]
        if r.get("doi") is not None:
            node_data["doi"] = r["doi"]
        nodes.append(node_data)
        valid_node_ids.add(r["id"])
        
    edges = []
    for r in edges_res:
        if r["from_id"] in valid_node_ids and r["to_id"] in valid_node_ids:
            edges.append({
                "from": r["from_id"],
                "to": r["to_id"],
                "type": r["type"]
            })
            
    return {"nodes": nodes, "edges": edges}

@router.get("/documents/{id}/text")
def get_document_text(id: str, session_id: Optional[str] = Query(None)):
    # Validate session ownership if session_id is provided
    if session_id:
        if neo4j_client.is_mock():
            doc = neo4j_client.mock_nodes.get(id)
            if doc and doc.get("session_id") != session_id:
                raise HTTPException(status_code=403, detail="Access denied. Document does not belong to this session.")
        else:
            query = "MATCH (d:Document {id: $id}) RETURN d.session_id as session_id"
            res = neo4j_client.run_query(query, {"id": id})
            if res and res[0].get("session_id") != session_id:
                raise HTTPException(status_code=403, detail="Access denied. Document does not belong to this session.")

    query = "MATCH (d:Document {id: $id}) RETURN d.title as title, d.storage_url as url"
    res = neo4j_client.run_query(query, {"id": id})
    if not res:
        raise HTTPException(status_code=404, detail="Document not found.")
    
    try:
        title = res[0]["title"]
        url = res[0].get("url") or ""
        blob_path = _blob_path_from_storage_url(url)
        if blob_path and vercel_blob_client.is_configured():
            file_bytes = vercel_blob_client.get(blob_path)
        else:
            path = f"uploads/{id}_{title}"
            file_bytes = supabase_client.download_file("documents", path)
        
        from server.utils.text_cleaner import stream_clean_pdf_text_from_bytes
        from fastapi.responses import StreamingResponse
        
        def text_generator():
            try:
                for chunk in stream_clean_pdf_text_from_bytes(file_bytes, chunk_size=10):
                    yield chunk
            except Exception as e:
                logger.error(f"Failed to parse PDF bytes mid-stream for document {id}: {e}")
                yield f"\n\n[Error: Failed to finish parsing document: {str(e)}]\n"
                
        return StreamingResponse(text_generator(), media_type="text/plain")
    except Exception as e:
        logger.error(f"Failed to fetch PDF bytes for document {id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch document: {str(e)}")

@router.delete("/sessions/{session_id}")
def delete_session_data(session_id: str):
    import os
    # 1. Fetch document nodes in this session to get their paths for deletion from Supabase
    if neo4j_client.is_mock():
        doc_nodes = [
            n for n in neo4j_client.mock_nodes.values() 
            if n.get("session_id") == session_id and n.get("label") == "Document"
        ]
    else:
        query = "MATCH (d:Document {session_id: $session_id}) RETURN d.storage_url as url"
        res = neo4j_client.run_query(query, {"session_id": session_id})
        doc_nodes = [{"storage_url": r["url"]} for r in res]

    # Delete files from Supabase/mock storage
    for doc in doc_nodes:
        url = doc.get("storage_url", "")
        if url:
            blob_path = _blob_path_from_storage_url(url)
            if blob_path and vercel_blob_client.is_configured():
                vercel_blob_client.delete(blob_path)
            elif url.startswith("file:///"):
                filename = os.path.basename(url)
                supabase_client.delete_file("documents", filename)
            else:
                match = re.search(r'documents/(uploads/.*)', url)
                if match:
                    path = match.group(1)
                    supabase_client.delete_file("documents", path)

    # 2. Delete nodes/edges from Neo4j / mock
    if neo4j_client.is_mock():
        deleted_ids = set()
        for nid, n in list(neo4j_client.mock_nodes.items()):
            if n.get("session_id") == session_id:
                deleted_ids.add(nid)
                neo4j_client.mock_nodes.pop(nid)
        
        neo4j_client.mock_edges = [
            e for e in neo4j_client.mock_edges
            if e["from"] not in deleted_ids and e["to"] not in deleted_ids
        ]
    else:
        neo4j_client.run_query(
            "MATCH (n) WHERE n.session_id = $session_id DETACH DELETE n",
            {"session_id": session_id}
        )

    return {"status": "success", "message": f"Deleted session {session_id} data successfully."}

@router.get("/sessions/{session_id}/documents")
def get_session_documents(session_id: str):
    if neo4j_client.is_mock():
        docs = []
        for n in neo4j_client.mock_nodes.values():
            if n.get("label") == "Document" and n.get("session_id") == session_id:
                docs.append({
                    "id": n["id"],
                    "title": n.get("title", "Document"),
                    "status": n.get("status", "done"),
                    "progress_pct": n.get("progress_pct", 100)
                })
        if not docs:
            persisted_docs = _load_json_state("session-docs", session_id)
            if persisted_docs:
                return persisted_docs
        return docs

    # Real Neo4j Mode
    query = """
    MATCH (d:Document {session_id: $session_id})
    RETURN d.id as id, d.title as title, d.status as status, d.progress_pct as progress_pct
    """
    res = neo4j_client.run_query(query, {"session_id": session_id})
    return [
        {
            "id": r["id"],
            "title": r["title"] or "Untitled Document",
            "status": r["status"] or "done",
            "progress_pct": r["progress_pct"] or 100
        }
        for r in res
    ]

@router.delete("/documents/{doc_id}")
def delete_document(doc_id: str, session_id: Optional[str] = Query(None)):
    delete_document_internal(doc_id, session_id)
    return {"status": "success", "message": f"Document {doc_id} deleted successfully."}

