import io
import uuid
import datetime
import logging
from fastapi import APIRouter, UploadFile, File, BackgroundTasks, HTTPException
from pydantic import BaseModel
from pypdf import PdfReader

from api.utils.neo4j_client import neo4j_client
from api.utils.supabase_client import supabase_client
from api.utils.llm_client import llm_client, calculate_entity_quality, singularize_concept_name, normalize_and_clean_concept_name
from api.utils.sequence_parser import parse_learning_sequences
import re

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
    
    for node in nodes:
        name = node.get("name")
        if not name:
            continue
        matched = False
        for cluster in clusters:
            rep_node = cluster[0]
            if are_semantically_similar(name, rep_node["name"]):
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
            "difficulty_level": rep.get("difficulty_level", "Beginner")
        }
        for k, v in rep.items():
            if k not in canonical_node:
                canonical_node[k] = v
        canonical_nodes.append(canonical_node)
        
        for node in cluster:
            name_mapping[node["name"].lower().strip()] = canonical_node["name"]
            
    return canonical_nodes, name_mapping

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
        
        # Identify main topic of the document
        main_topic_info = llm_client.identify_main_topic(text[:15000], filename)
        logger.info(f"Identified main topic: {main_topic_info}")
        
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
                extracted_nodes = result.get("nodes", [])
                extracted_rels = result.get("relationships", [])
                
                # Clean node names immediately after extraction
                for node in extracted_nodes:
                    node["name"] = normalize_and_clean_concept_name(node.get("name", ""))
                # Clean relationship from/to names
                for rel in extracted_rels:
                    rel["from"] = normalize_and_clean_concept_name(rel.get("from", ""))
                    rel["to"] = normalize_and_clean_concept_name(rel.get("to", ""))
                
                all_nodes.extend(extracted_nodes)
                all_relationships.extend(extracted_rels)
            except Exception as e:
                logger.error(f"Error extracting chunk {i} for doc {doc_id}: {e}")
                # Retry once
                try:
                    result = llm_client.extract_graph_from_chunk(chunk)
                    extracted_nodes = result.get("nodes", [])
                    extracted_rels = result.get("relationships", [])
                    
                    # Clean node names immediately after extraction
                    for node in extracted_nodes:
                        node["name"] = normalize_and_clean_concept_name(node.get("name", ""))
                    # Clean relationship from/to names
                    for rel in extracted_rels:
                        rel["from"] = normalize_and_clean_concept_name(rel.get("from", ""))
                        rel["to"] = normalize_and_clean_concept_name(rel.get("to", ""))
                    
                    all_nodes.extend(extracted_nodes)
                    all_relationships.extend(extracted_rels)
                except Exception:
                    logger.error(f"Retry failed for chunk {i}. Skipping.")
            
            # Update progress
            current_progress = int(40 + (i + 1) * step_increment)
            extraction_status_cache[doc_id]["progress_pct"] = min(90, current_progress)
            
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

        # Check multi-document mode config
        from api.config import config
        multi_doc_mode = getattr(config, "MULTI_DOCUMENT_MODE", False)

        if not multi_doc_mode:
            # Clear all cached data, previous uploads, embeddings, vector-store entries, and session memory
            # keeping only the current doc_id status to keep it polling!
            for k in list(extraction_status_cache.keys()):
                if k != doc_id:
                    extraction_status_cache.pop(k, None)
            
            # Clear files from storage
            try:
                supabase_client.clear_bucket("documents")
            except Exception as e:
                logger.error(f"Failed to clear storage bucket: {e}")

            if neo4j_client.is_mock():
                # Clear mock nodes/edges but preserve the current Document node
                current_doc = neo4j_client.mock_nodes.get(doc_id)
                neo4j_client.mock_nodes.clear()
                neo4j_client.mock_edges.clear()
                if current_doc:
                    neo4j_client.mock_nodes[doc_id] = current_doc
            else:
                # Delete all nodes except the current Document node
                neo4j_client.run_query(
                    "MATCH (n) WHERE NOT (n:Document AND n.id = $doc_id) DETACH DELETE n",
                    {"doc_id": doc_id}
                )

        # 4. Idempotent Merge Writes to Neo4j
        # Prepare the central node
        central_node = {
            "label": "Topic",
            "name": main_topic_info.get("name", "Document Main Topic"),
            "description": main_topic_info.get("description", ""),
            "difficulty_level": "Beginner"
        }
        
        # Add central node to the list of nodes
        all_nodes.append(central_node)
        
        # Run global semantic merging and clustering
        canonical_nodes, name_mapping = cluster_and_merge_nodes(all_nodes)
        
        # Verify that every graph node exists in the current document text
        original_count = len(canonical_nodes)
        canonical_nodes = [n for n in canonical_nodes if n.get("name", "").lower().strip() in text.lower()]
        logger.info(f"Filtered out {original_count - len(canonical_nodes)} nodes not present in the document text.")
        
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
            
            if not from_name or not to_name:
                continue
                
            canonical_from = name_mapping.get(from_name.lower().strip(), from_name)
            canonical_to = name_mapping.get(to_name.lower().strip(), to_name)
            
            if canonical_from.lower().strip() == canonical_to.lower().strip():
                continue
                
            rel_key = (canonical_from, canonical_to, rel_type)
            if rel_key not in seen_rels:
                seen_rels.add(rel_key)
                merged_relationships.append({
                    "from": canonical_from,
                    "to": canonical_to,
                    "type": rel_type
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

        concepts_keywords = [n for n in canonical_nodes if n.get("label") in ["Concept", "Keyword"]]
        other_nodes = [n for n in canonical_nodes if n.get("label") not in ["Concept", "Keyword"]]

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

        # Keep top 40 concepts/keywords
        kept_concepts_keywords = concepts_keywords[:40]
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
        
        # Write nodes to Neo4j
        for node in canonical_nodes:
            label = node.get("label", "Concept")
            if label not in ["Concept", "Topic", "Keyword", "Paper", "Author"]:
                label = "Concept"
            name = node.get("name").strip()
            desc = node.get("description", "").strip()
            
            node_id = str(uuid.uuid4())
            
            # Check multi-document mode config
            from api.config import config
            multi_doc_mode = getattr(config, "MULTI_DOCUMENT_MODE", False)

            # Neo4j query
            if label == "Paper":
                year = node.get("year")
                doi = node.get("doi")
                if multi_doc_mode:
                    query = """
                    MERGE (n:Paper {name: $name})
                    ON CREATE SET n.id = $id, n.title = $name, n.description = $description, n.difficulty_level = 'Beginner', n.doc_id = $doc_id, n.year = $year, n.doi = $doi
                    ON MATCH SET n.title = $name, n.description = CASE WHEN n.description IS NULL OR n.description = '' THEN $description ELSE n.description END, n.year = $year, n.doi = $doi
                    RETURN n.id as node_id
                    """
                else:
                    query = """
                    MERGE (n:Paper {name: $name, doc_id: $doc_id})
                    ON CREATE SET n.id = $id, n.title = $name, n.description = $description, n.difficulty_level = 'Beginner', n.year = $year, n.doi = $doi
                    ON MATCH SET n.title = $name, n.description = CASE WHEN n.description IS NULL OR n.description = '' THEN $description ELSE n.description END, n.year = $year, n.doi = $doi
                    RETURN n.id as node_id
                    """
            else:
                if multi_doc_mode:
                    query = f"""
                    MERGE (n:{label} {{name: $name}})
                    ON CREATE SET n.id = $id, n.description = $description, n.difficulty_level = 'Beginner', n.doc_id = $doc_id
                    ON MATCH SET n.description = CASE WHEN n.description IS NULL OR n.description = '' THEN $description ELSE n.description END
                    RETURN n.id as node_id
                    """
                else:
                    query = f"""
                    MERGE (n:{label} {{name: $name, doc_id: $doc_id}})
                    ON CREATE SET n.id = $id, n.description = $description, n.difficulty_level = 'Beginner'
                    ON MATCH SET n.description = CASE WHEN n.description IS NULL OR n.description = '' THEN $description ELSE n.description END
                    RETURN n.id as node_id
                    """
            
            res = neo4j_client.run_query(query, {
                "name": name, 
                "id": node_id, 
                "description": desc, 
                "doc_id": doc_id,
                "year": node.get("year"),
                "doi": node.get("doi")
            })
            
            # Capture the resolved node ID
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
                existing_id = None
                for nid, mn in neo4j_client.mock_nodes.items():
                    if mn.get("label") == label and mn.get("name", "").lower() == name.lower():
                        if multi_doc_mode or mn.get("doc_id") == doc_id:
                            existing_id = nid
                            break
                if existing_id:
                    resolved_id = existing_id
                    if not neo4j_client.mock_nodes[resolved_id].get("description"):
                        neo4j_client.mock_nodes[resolved_id]["description"] = desc
                else:
                    resolved_id = node_id
                    node_data = {
                        "id": resolved_id,
                        "label": label,
                        "name": name,
                        "description": desc,
                        "difficulty_level": "Beginner",
                        "doc_id": doc_id
                    }
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
                    if n.get("name", "").lower() == from_name.lower():
                        if multi_doc_mode or n.get("doc_id") == doc_id:
                            from_id = nid
                    if n.get("name", "").lower() == to_name.lower():
                        if multi_doc_mode or n.get("doc_id") == doc_id:
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
        # Read file bytes
        file_bytes = await file.read()

        # Clear state if not multi-document mode
        from api.config import config
        multi_doc_mode = getattr(config, "MULTI_DOCUMENT_MODE", False)
        if not multi_doc_mode:
            extraction_status_cache.clear()
            try:
                supabase_client.clear_bucket("documents")
            except Exception as e:
                logger.error(f"Failed to clear storage bucket: {e}")
            if neo4j_client.is_mock():
                neo4j_client.mock_nodes.clear()
                neo4j_client.mock_edges.clear()
            else:
                try:
                    neo4j_client.run_query("MATCH (n) DETACH DELETE n")
                except Exception as e:
                    logger.error(f"Failed to clear Neo4j on upload: {e}")
        
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
    from api.config import config
    multi_doc_mode = getattr(config, "MULTI_DOCUMENT_MODE", False)

    if neo4j_client.is_mock():
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
                    n_copy = dict(n)
                    if not n_copy.get("name") and n_copy.get("title"):
                        n_copy["name"] = n_copy["title"]
                    ml_nodes.append(n_copy)
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
                n_copy = dict(n)
                if not n_copy.get("name") and n_copy.get("title"):
                    n_copy["name"] = n_copy["title"]
                doc_nodes.append(n_copy)
                
        doc_node_ids_filtered = {n["id"] for n in doc_nodes}
        doc_edges = [
            e for e in neo4j_client.mock_edges 
            if e["type"] != "CONTAINS" and e["from"] in doc_node_ids_filtered and e["to"] in doc_node_ids_filtered
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
