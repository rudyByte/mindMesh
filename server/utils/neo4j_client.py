import logging
from neo4j import GraphDatabase
from server.config import config

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("neo4j_client")

class Neo4jClient:
    def __init__(self):
        self._driver = None
        self._is_mock = False
        self.mock_nodes = {}
        self.mock_edges = []
        self.connect()

    def connect(self):
        try:
            # Check if using default local dummy configs, trigger mock early
            if "localhost" in config.NEO4J_URI and config.NEO4J_PASSWORD == "password":
                logger.warning("Default localhost credentials detected. Starting in mock mode.")
                self._is_mock = True
                self._seed_mock_data()
                return

            self._driver = GraphDatabase.driver(
                config.NEO4J_URI,
                auth=(config.NEO4J_USER, config.NEO4J_PASSWORD)
            )
            self._driver.verify_connectivity()
            self._is_mock = False
            logger.info("Successfully connected to Neo4j database.")
        except Exception as e:
            logger.warning(f"Failed to connect to Neo4j database: {e}. Falling back to in-memory Mock mode.")
            self._is_mock = True
            self._driver = None
            # Seed basic mock data so mock mode starts with something visual
            self._seed_mock_data()

    def close(self):
        if self._driver:
            self._driver.close()

    def is_mock(self) -> bool:
        return self._is_mock

    def ping(self) -> bool:
        if self._is_mock:
            return True
        try:
            with self._driver.session() as session:
                session.run("RETURN 1")
            return True
        except Exception:
            return False

    def run_query(self, query: str, parameters: dict = None):
        if self._is_mock:
            logger.info(f"[MOCK] Running Cypher query: {query} with params: {parameters}")
            return self._run_mock_query(query, parameters)
        
        with self._driver.session() as session:
            result = session.run(query, parameters or {})
            return [record.data() for record in result]

    def execute_migration(self, cypher_file_path: str):
        if self._is_mock:
            logger.info(f"[MOCK] Skipping migration execution for file {cypher_file_path}")
            return
        
        try:
            with open(cypher_file_path, 'r') as f:
                content = f.read()
            queries = [q.strip() for q in content.split(';') if q.strip()]
            with self._driver.session() as session:
                for q in queries:
                    session.run(q)
            logger.info(f"Successfully ran migration {cypher_file_path}")
        except Exception as e:
            logger.error(f"Failed to execute migration {cypher_file_path}: {e}")

    def _seed_mock_data(self):
        # Default mock concepts mirroring seed.cypher exactly
        self.mock_nodes = {}
        self.mock_edges = []

    def _run_mock_query(self, query: str, parameters: dict = None):
        query_upper = query.upper()
        params = parameters or {}

        if "RETURN 1" in query_upper:
            return [{"1": 1}]

        if "DETACH DELETE N" in query_upper and "MATCH" in query_upper:
            self.mock_nodes.clear()
            self.mock_edges.clear()
            return []

        if "COUNT(N)" in query_upper and "RETURN" in query_upper:
            return [{"count": len(self.mock_nodes)}]

        # 1. Update/SET queries (e.g. status updates)
        if "SET " in query_upper and "MERGE" not in query_upper:
            doc_id = params.get("doc_id") or params.get("id")
            if doc_id and doc_id in self.mock_nodes:
                for k, v in params.items():
                    if k not in ["doc_id", "id"]:
                        self.mock_nodes[doc_id][k] = v
                if "STATUS = 'DONE'" in query_upper:
                    self.mock_nodes[doc_id]["status"] = "done"
                    self.mock_nodes[doc_id]["progress_pct"] = 100
                elif "STATUS = 'ERROR'" in query_upper:
                    self.mock_nodes[doc_id]["status"] = "error"
                return [{"d": self.mock_nodes[doc_id]}]
            return []

        # 2. Document insertion
        if "MERGE (D:DOCUMENT" in query_upper:
            doc_id = params.get("id", "doc-1")
            self.mock_nodes[doc_id] = {
                "id": doc_id,
                "label": "Document",
                "title": params.get("title", "Document"),
                "type": params.get("type", "pdf"),
                "status": "processing",
                "progress_pct": 10,
                "upload_date": params.get("upload_date"),
                "storage_url": params.get("storage_url")
            }
            return [{"d": self.mock_nodes[doc_id]}]

        # 3. Concept / Paper / Author / Note / Highlight / Citation insertion
        if ("MERGE" in query_upper or "CREATE" in query_upper) and "->" not in query_upper:
            label = "Concept"
            if ":PAPER" in query_upper:
                label = "Paper"
            elif ":AUTHOR" in query_upper:
                label = "Author"
            elif ":NOTE" in query_upper:
                label = "Note"
            elif ":HIGHLIGHT" in query_upper:
                label = "Highlight"
            elif ":CITATION" in query_upper:
                label = "Citation"
            elif ":KEYWORD" in query_upper:
                label = "Keyword"
            elif ":TOPIC" in query_upper:
                label = "Topic"
            elif ":SUBTOPIC" in query_upper:
                label = "Subtopic"
            elif ":TECHNOLOGY" in query_upper:
                label = "Technology"
            elif ":FRAMEWORK" in query_upper:
                label = "Framework"
            elif ":APPLICATION" in query_upper:
                label = "Application"
            elif ":INSTITUTION" in query_upper:
                label = "Institution"
            elif ":METHOD" in query_upper:
                label = "Method"
            elif ":DATASET" in query_upper:
                label = "Dataset"
            
            name = params.get("name") or params.get("title") or "Node"
            node_id = params.get("id") or f"mock-n-{len(self.mock_nodes) + 1}"
            
            existing_id = None
            if "MERGE" in query_upper:
                # Look for existing node with matching name/title and session_id / doc_id
                name_val = name.strip().lower()
                sess_val = params.get("session_id")
                d_val = params.get("doc_id")
                id_val = params.get("id")
                
                for nid, mn in self.mock_nodes.items():
                    mn_label = mn.get("label", "Concept")
                    is_concept_like = (
                        (label in ["Concept", "Topic", "Subtopic", "Keyword", "Author", "Method", "Dataset", "Technology", "Framework", "Application", "Institution"] and mn_label in ["Concept", "Topic", "Subtopic", "Keyword", "Author", "Method", "Dataset", "Technology", "Framework", "Application", "Institution"])
                        or label == mn_label
                    )
                    if is_concept_like:
                        mn_name = (mn.get("name") or mn.get("title") or "").strip().lower()
                        if mn_name == name_val:
                            # Match session or doc
                            session_match = True
                            doc_match = True
                            if sess_val is not None:
                                session_match = (mn.get("session_id") == sess_val)
                            else:
                                if d_val is not None or mn.get("doc_id") is not None:
                                    doc_match = (mn.get("doc_id") == d_val)
                                
                            if session_match and doc_match:
                                existing_id = nid
                                break
                    elif id_val and mn.get("id") == id_val:
                        existing_id = nid
                        break

            if existing_id:
                node_id = existing_id
                # Update attributes on existing node
                for k, v in params.items():
                    if k not in ["id", "label"]:
                        self.mock_nodes[node_id][k] = v
            else:
                node_data = {
                    "id": node_id,
                    "label": label,
                    "name": name,
                    "title": name,
                    "description": params.get("description", ""),
                    "difficulty_level": params.get("difficulty_level", "Beginner")
                }
                # Copy all additional fields from params to mock data
                for k, v in params.items():
                    if k not in node_data:
                        node_data[k] = v
                        
                self.mock_nodes[node_id] = node_data
                
            return [{"node_id": node_id, "n": self.mock_nodes[node_id]}]

        # 3.1 Relationship insertion
        if "MERGE" in query_upper and "->" in query_upper:
            if "CONTAINS" in query_upper:
                doc_id = params.get("doc_id")
                node_id = params.get("node_id")
                if doc_id and node_id:
                    self.mock_edges.append({
                        "from": doc_id,
                        "to": node_id,
                        "type": "CONTAINS"
                    })
            return []

        # 4. MATCH/Retrieve queries
        if "MATCH" in query_upper:
            # Check if it's querying a Document by ID (for text/status)
            if "DOCUMENT" in query_upper and ("ID" in query_upper or "DOC_ID" in query_upper) and "CONTAINS" not in query_upper:
                doc_id = params.get("id") or params.get("doc_id")
                if doc_id and doc_id in self.mock_nodes:
                    doc = self.mock_nodes[doc_id]
                    return [{
                        "status": doc.get("status", "done"),
                        "progress_pct": doc.get("progress_pct", 100),
                        "error_msg": doc.get("error_msg"),
                        "title": doc.get("title", "Document"),
                        "storage_url": doc.get("storage_url", "")
                    }]
                return []

            # Check if it's querying for a list of concepts (for concept-linking)
            if "CONCEPT" in query_upper and "RETURN" in query_upper and "CONTAINS" not in query_upper:
                return [{"id": node["id"], "name": node["name"]} for node in self.mock_nodes.values() if node.get("label") in ["Topic", "Subtopic", "Concept", "Technology", "Framework", "Application", "Paper", "Author", "Keyword"]]

            # Expand graph paths (Sprint 2 expand / traverse)
            if any(term in query_upper for term in ["PREREQUISITE_OF", "RELATED_TO", "EXTENDS", "DEPENDS_ON", "USES", "CITES", "CONTAINS", "PATH"]):
                target_id = params.get("id") or params.get("node_id")
                depth = params.get("depth", 1)
                mode = params.get("mode", "basic")
                doc_id = params.get("doc_id") or params.get("document_id")
                session_id = params.get("session_id")
                
                nodes_to_return = {}
                edges_to_return = []
                
                # Retrieve valid node IDs for this document/session
                doc_node_ids = set()
                if session_id:
                    for nid, n in self.mock_nodes.items():
                        if n.get("session_id") == session_id:
                            doc_node_ids.add(nid)
                elif doc_id:
                    if doc_id == "doc-1":
                        for nid, n in self.mock_nodes.items():
                            if n.get("label") != "Document":
                                doc_node_ids.add(nid)
                    else:
                        for edge in self.mock_edges:
                            if edge["from"] == doc_id and edge["type"] == "CONTAINS":
                                doc_node_ids.add(edge["to"])
                        for nid, n in self.mock_nodes.items():
                            if n.get("doc_id") == doc_id:
                                doc_node_ids.add(nid)
                else:
                    doc_node_ids = set(self.mock_nodes.keys())

                if target_id not in self.mock_nodes or target_id not in doc_node_ids:
                    return [{"nodes": [], "edges": []}]
                
                visited_nodes = {target_id}
                current_frontier = {target_id}
                nodes_to_return = {target_id: self.mock_nodes[target_id]}
                
                # Pre-filter edges to only those relevant to this document/session and mode
                valid_edges = []
                for edge in self.mock_edges:
                    if edge["type"] == "CONTAINS" and (edge["from"] == doc_id or edge["from"] == "doc-1" or (edge["from"] in self.mock_nodes and self.mock_nodes[edge["from"]].get("label") == "Document")):
                        continue
                    if mode == "basic" and edge["type"] != "PREREQUISITE_OF":
                        continue
                    if session_id and edge.get("session_id") != session_id:
                        continue
                    elif doc_id and doc_id != "doc-1" and edge.get("doc_id") != doc_id:
                        continue
                    if edge["from"] in doc_node_ids and edge["to"] in doc_node_ids:
                        valid_edges.append(edge)
                
                # BFS to expand frontier up to 'depth' hops
                for _ in range(depth):
                    next_frontier = set()
                    for edge in valid_edges:
                        if edge["from"] in current_frontier and edge["to"] not in visited_nodes:
                            next_frontier.add(edge["to"])
                        elif edge["to"] in current_frontier and edge["from"] not in visited_nodes:
                            next_frontier.add(edge["from"])
                    
                    for nid in next_frontier:
                        visited_nodes.add(nid)
                        nodes_to_return[nid] = self.mock_nodes[nid]
                    
                    current_frontier = next_frontier
                    if not current_frontier:
                        break
                
                # Collect all edges that exist completely within the visited subgraph
                edges_to_return = []
                for edge in valid_edges:
                    if edge["from"] in visited_nodes and edge["to"] in visited_nodes:
                        edges_to_return.append(edge)

                return [{"nodes": list(nodes_to_return.values()), "edges": edges_to_return}]

            # Document Contains subgraph
            if "DOCUMENT" in query_upper and "CONTAINS" in query_upper:
                doc_id = params.get("doc_id") or params.get("document_id") or "doc-1"
                doc_node_ids = set()
                if doc_id == "doc-1":
                    for nid, n in self.mock_nodes.items():
                        if n.get("label") != "Document":
                            doc_node_ids.add(nid)
                else:
                    for edge in self.mock_edges:
                        if edge["from"] == doc_id and edge["type"] == "CONTAINS":
                            doc_node_ids.add(edge["to"])
                    for nid, n in self.mock_nodes.items():
                        if n.get("doc_id") == doc_id:
                            doc_node_ids.add(nid)
                
                doc_nodes = []
                for nid, n in self.mock_nodes.items():
                    if nid in doc_node_ids:
                        n_copy = dict(n)
                        if not n_copy.get("name") and n_copy.get("title"):
                            n_copy["name"] = n_copy["title"]
                        doc_nodes.append(n_copy)
                
                if doc_id == "doc-1":
                    doc_edges = [
                        e for e in self.mock_edges 
                        if e["type"] != "CONTAINS" and e["from"] in doc_node_ids and e["to"] in doc_node_ids
                    ]
                else:
                    doc_edges = [
                        e for e in self.mock_edges 
                        if e["type"] != "CONTAINS" and e.get("doc_id") == doc_id
                    ]
                return [{"nodes": doc_nodes, "edges": doc_edges}]
            
            # Fetch single node details by ID
            if "ID" in query_upper and "DOCUMENT" not in query_upper:
                node_id = params.get("id") or params.get("node_id")
                doc_id = params.get("doc_id") or params.get("document_id")
                session_id = params.get("session_id")
                if node_id and node_id in self.mock_nodes:
                    n = self.mock_nodes[node_id]
                    
                    # Validate doc_id/session_id ownership in mock
                    if session_id:
                        if n.get("session_id") != session_id:
                            return []
                    elif doc_id:
                        is_valid = False
                        if doc_id == "doc-1":
                            is_valid = True
                        else:
                            has_contains = any(
                                e["from"] == doc_id and e["to"] == node_id and e["type"] == "CONTAINS"
                                for e in self.mock_edges
                            )
                            if has_contains or n.get("doc_id") == doc_id:
                                is_valid = True
                        if not is_valid:
                            return []

                    name = n.get("name") or n.get("title") or "Unknown"
                    return [{
                        "label": n.get("label", "Concept"),
                        "id": n.get("id"),
                        "name": name,
                        "description": n.get("description", ""),
                        "difficulty_level": n.get("difficulty_level", "Beginner"),
                        "title": n.get("title"),
                        "year": n.get("year"),
                        "doi": n.get("doi")
                    }]
                return []

            # List all nodes fallback
            if "MATCH (N) RETURN" in query_upper or "MATCH (N:CONCEPT)" in query_upper:
                doc_id = params.get("doc_id") or params.get("document_id")
                nodes_list = []
                for node in self.mock_nodes.values():
                    if doc_id and doc_id != "doc-1" and node.get("doc_id") != doc_id:
                        continue
                    nodes_list.append({"n": node})
                return nodes_list

        return []

neo4j_client = Neo4jClient()
