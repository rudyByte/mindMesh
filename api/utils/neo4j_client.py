import logging
from neo4j import GraphDatabase
from api.config import config

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
        # Default mock concepts
        self.mock_nodes = {
            "c-1": {"id": "c-1", "label": "Concept", "name": "Linear Algebra", "description": "Vectors, matrices, and linear transforms.", "difficulty_level": "Beginner"},
            "c-2": {"id": "c-2", "label": "Concept", "name": "Calculus", "description": "Limits, derivatives, integrals, and approximation.", "difficulty_level": "Beginner"},
            "c-3": {"id": "c-3", "label": "Concept", "name": "Probability & Statistics", "description": "Random variables, Bayes rule, and estimations.", "difficulty_level": "Beginner"},
            "c-4": {"id": "c-4", "label": "Concept", "name": "Gradient Descent", "description": "Optimization algorithm to minimize loss.", "difficulty_level": "Intermediate"},
            "c-5": {"id": "c-5", "label": "Concept", "name": "Neural Networks", "description": "Computational graphs modeled on biological brains.", "difficulty_level": "Intermediate"},
            "c-6": {"id": "c-6", "label": "Concept", "name": "Transformers", "description": "Self-attention mechanism architectures.", "difficulty_level": "Advanced"},
            "p-1": {"id": "p-1", "label": "Paper", "title": "Attention Is All You Need", "year": 2017, "doi": "10.48550/arXiv.1706.03762"},
        }
        self.mock_edges = [
            {"from": "c-1", "to": "c-4", "type": "PREREQUISITE_OF"},
            {"from": "c-2", "to": "c-4", "type": "PREREQUISITE_OF"},
            {"from": "c-4", "to": "c-5", "type": "PREREQUISITE_OF"},
            {"from": "c-5", "to": "c-6", "type": "PREREQUISITE_OF"},
            {"from": "p-1", "to": "c-6", "type": "USES_METHOD"},
        ]

    def _run_mock_query(self, query: str, parameters: dict = None):
        query_upper = query.upper()
        params = parameters or {}

        if "RETURN 1" in query_upper:
            return [{"1": 1}]

        if "MERGE (D:DOCUMENT" in query_upper:
            doc_id = params.get("id", "doc-1")
            self.mock_nodes[doc_id] = {
                "id": doc_id,
                "label": "Document",
                "title": params.get("title", "Document"),
                "type": params.get("type", "pdf"),
                "upload_date": params.get("upload_date"),
                "storage_url": params.get("storage_url")
            }
            return [{"d": self.mock_nodes[doc_id]}]

        if "MERGE" in query_upper or "CREATE" in query_upper:
            # We dynamically intercept inserts from Sprint 1 Graph Extraction
            # E.g. MERGE (n:Concept {name: $name}) ...
            label = "Concept"
            if ":PAPER" in query_upper:
                label = "Paper"
            elif ":AUTHOR" in query_upper:
                label = "Author"
            
            # Simple simulation of adding node
            name = params.get("name") or params.get("title") or "Node"
            node_id = params.get("id") or f"mock-n-{len(self.mock_nodes) + 1}"
            
            self.mock_nodes[node_id] = {
                "id": node_id,
                "label": label,
                "name": name,
                "title": name,
                "description": params.get("description", ""),
                "difficulty_level": params.get("difficulty_level", "Beginner")
            }
            return [{"n": self.mock_nodes[node_id]}]

        # Retrieve nodes/edges matching conditions
        if "MATCH" in query_upper:
            if "PREREQUISITE_OF" in query_upper or "RELATED_TO" in query_upper or "EXTENDS" in query_upper:
                # Return paths for SPRINT 2 expand
                result = []
                target_id = params.get("id")
                depth = params.get("depth", 1)
                
                # Simple BFS/DFS in memory for Mock paths
                visited = set()
                queue = [(target_id, 0)]
                nodes_to_return = {}
                edges_to_return = []
                
                if target_id in self.mock_nodes:
                    nodes_to_return[target_id] = self.mock_nodes[target_id]
                
                # Gather links up to depth
                for edge in self.mock_edges:
                    # Basic direction expansion
                    # Incoming for Prereq (Basic), Outgoing or Undirected for Advanced
                    if edge["from"] == target_id or edge["to"] == target_id:
                        from_node = self.mock_nodes.get(edge["from"])
                        to_node = self.mock_nodes.get(edge["to"])
                        if from_node and to_node:
                            nodes_to_return[edge["from"]] = from_node
                            nodes_to_return[edge["to"]] = to_node
                            edges_to_return.append(edge)

                return [{"nodes": list(nodes_to_return.values()), "edges": edges_to_return}]

            if "DOCUMENT" in query_upper and "CONTAINS" in query_upper:
                # Return document-specific subgraph
                doc_id = params.get("id")
                # Return all mock nodes as part of the document
                return [{"nodes": list(self.mock_nodes.values()), "edges": self.mock_edges}]
            
            if "MATCH (N) RETURN" in query_upper or "MATCH (N:CONCEPT)" in query_upper:
                # List all nodes
                return [{"n": node} for node in self.mock_nodes.values()]

        return []

neo4j_client = Neo4jClient()
