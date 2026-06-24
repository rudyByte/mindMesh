import logging
from neo4j import GraphDatabase
from config import config

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
        self.mock_nodes = {
            "doc-1": {
                "id": "doc-1",
                "label": "Document",
                "title": "MachineLearningTextbook.pdf",
                "type": "pdf",
                "status": "done",
                "progress_pct": 100,
                "upload_date": "2026-06-22T04:12:10Z",
                "storage_url": "mock-url"
            },
            "c-linear-algebra": {"id": "c-linear-algebra", "label": "Concept", "name": "Linear Algebra", "description": "Vectors, matrices, linear transforms, and vector spaces.", "difficulty_level": "Beginner"},
            "c-calculus": {"id": "c-calculus", "label": "Concept", "name": "Calculus", "description": "Limits, derivatives, integrals, and approximation methods.", "difficulty_level": "Beginner"},
            "c-probability-stats": {"id": "c-probability-stats", "label": "Concept", "name": "Probability & Statistics", "description": "Random variables, distributions, Bayes rule, and estimations.", "difficulty_level": "Beginner"},
            "c-matrix-operations": {"id": "c-matrix-operations", "label": "Concept", "name": "Matrix Operations", "description": "Matrix addition, multiplication, inversion, and determinants.", "difficulty_level": "Beginner"},
            "c-partial-derivatives": {"id": "c-partial-derivatives", "label": "Concept", "name": "Partial Derivatives", "description": "Derivatives of multi-variable functions with respect to single variables.", "difficulty_level": "Beginner"},
            "c-chain-rule": {"id": "c-chain-rule", "label": "Concept", "name": "Chain Rule", "description": "Formula for computing the derivative of the composition of two or more functions.", "difficulty_level": "Beginner"},
            "c-bayes-theorem": {"id": "c-bayes-theorem", "label": "Concept", "name": "Bayes Theorem", "description": "Mathematical formula for determining conditional probabilities.", "difficulty_level": "Beginner"},
            "c-loss-function": {"id": "c-loss-function", "label": "Concept", "name": "Loss Function", "description": "Function that maps values of variables onto a real number representing cost.", "difficulty_level": "Beginner"},
            "c-gradient-descent": {"id": "c-gradient-descent", "label": "Concept", "name": "Gradient Descent", "description": "Optimization algorithm to minimize loss by moving in steepest descent direction.", "difficulty_level": "Intermediate"},
            "c-sgd": {"id": "c-sgd", "label": "Concept", "name": "Stochastic Gradient Descent", "description": "Iterative method for optimizing objective functions using sample subsets.", "difficulty_level": "Intermediate"},
            "c-optimization": {"id": "c-optimization", "label": "Concept", "name": "Optimization", "description": "Selecting the best element with regard to some criteria from alternatives.", "difficulty_level": "Intermediate"},
            "c-neural-networks": {"id": "c-neural-networks", "label": "Concept", "name": "Neural Networks", "description": "Computational models inspired by biological brains to recognize patterns.", "difficulty_level": "Intermediate"},
            "c-activation-functions": {"id": "c-activation-functions", "label": "Concept", "name": "Activation Functions", "description": "Functions defining output of a node given inputs.", "difficulty_level": "Intermediate"},
            "c-backpropagation": {"id": "c-backpropagation", "label": "Concept", "name": "Backpropagation", "description": "Algorithm for supervised learning of neural nets using gradient chain rule.", "difficulty_level": "Intermediate"},
            "c-regularization": {"id": "c-regularization", "label": "Concept", "name": "Regularization", "description": "Introducing information/constraints to prevent overfitting.", "difficulty_level": "Intermediate"},
            "c-sigmoid-relu": {"id": "c-sigmoid-relu", "label": "Concept", "name": "Sigmoid & ReLU", "description": "Common non-linear activation functions used to enable deep learning representation.", "difficulty_level": "Beginner"},
            "c-feedforward-networks": {"id": "c-feedforward-networks", "label": "Concept", "name": "Feedforward Networks", "description": "The simplest type of artificial neural network where connections do not form cycles.", "difficulty_level": "Intermediate"},
            "c-cnns": {"id": "c-cnns", "label": "Concept", "name": "Convolutional Neural Networks (CNNs)", "description": "Deep learning models designed for processing grid structured data like images.", "difficulty_level": "Advanced"},
            "c-rnns": {"id": "c-rnns", "label": "Concept", "name": "Recurrent Neural Networks (RNNs)", "description": "Neural networks where connections form a directed graph along a temporal sequence.", "difficulty_level": "Advanced"},
            "c-lstms": {"id": "c-lstms", "label": "Concept", "name": "LSTM & GRU", "description": "Recurrent neural network architectures designed to learn long-term dependencies.", "difficulty_level": "Advanced"},
            "c-seq2seq": {"id": "c-seq2seq", "label": "Concept", "name": "Sequence to Sequence", "description": "Models mapping variable-length input sequences to variable-length outputs.", "difficulty_level": "Advanced"},
            "c-attention": {"id": "c-attention", "label": "Concept", "name": "Attention Mechanism", "description": "Technique dynamically focusing on specific parts of inputs during output generation.", "difficulty_level": "Advanced"},
            "c-self-attention": {"id": "c-self-attention", "label": "Concept", "name": "Self-Attention", "description": "Attention mechanism relating different positions of a sequence to compute its representation.", "difficulty_level": "Advanced"},
            "c-multi-head-attention": {"id": "c-multi-head-attention", "label": "Concept", "name": "Multi-Head Attention", "description": "Running self-attention multiple times in parallel to project inputs into different subspaces.", "difficulty_level": "Advanced"},
            "c-transformers": {"id": "c-transformers", "label": "Concept", "name": "Transformers", "description": "Deep learning architecture relying solely on attention mechanisms for sequence processing.", "difficulty_level": "Advanced"},
            "c-positional-encoding": {"id": "c-positional-encoding", "label": "Concept", "name": "Positional Encoding", "description": "Injecting order/positional information to tokens since attention is permutation-invariant.", "difficulty_level": "Advanced"},
            "c-gnns": {"id": "c-gnns", "label": "Concept", "name": "Graph Neural Networks (GNNs)", "description": "Neural networks designed to perform inference on graph-structured data.", "difficulty_level": "Advanced"},
            "c-gcns": {"id": "c-gcns", "label": "Concept", "name": "Graph Convolutional Networks (GCNs)", "description": "Type of graph neural network utilizing spectral or spatial convolutions.", "difficulty_level": "Advanced"},
            "c-llms": {"id": "c-llms", "label": "Concept", "name": "Large Language Models", "description": "Generative models trained on massive text corpora to perform language tasks.", "difficulty_level": "Advanced"},
            "c-bert-gpt": {"id": "c-bert-gpt", "label": "Concept", "name": "BERT & GPT", "description": "Pioneering encoder/decoder transformer models for language representation and generation.", "difficulty_level": "Advanced"},
            "p-attention": {"id": "p-attention", "label": "Paper", "title": "Attention Is All You Need", "name": "Attention Is All You Need", "year": 2017, "doi": "10.48550/arXiv.1706.03762", "abstract": "The dominant sequence transduction models are based on complex recurrent or convolutional neural networks. We propose a new simple network architecture, the Transformer, based solely on attention mechanisms."},
            "p-resnet": {"id": "p-resnet", "label": "Paper", "title": "Deep Residual Learning for Image Recognition", "name": "Deep Residual Learning for Image Recognition", "year": 2015, "doi": "10.1109/CVPR.2016.90", "abstract": "Deeper neural networks are more difficult to train. We present a residual learning framework to ease the training of networks that are substantially deeper than those previously used."},
            "p-gcn": {"id": "p-gcn", "label": "Paper", "title": "Semi-Supervised Classification with Graph Convolutional Networks", "name": "Semi-Supervised Classification with Graph Convolutional Networks", "year": 2016, "doi": "10.48550/arXiv.1609.02907", "abstract": "We present a scalable approach for semi-supervised learning on graph-structured data that is based on an efficient variant of convolutional neural networks which operate directly on graphs."},
            "p-adam": {"id": "p-adam", "label": "Paper", "title": "Adam: A Method for Stochastic Optimization", "name": "Adam: A Method for Stochastic Optimization", "year": 2014, "doi": "10.48550/arXiv.1412.6980", "abstract": "We introduce Adam, an algorithm for first-order gradient-based optimization of stochastic objective functions, based on adaptive estimates of lower-order moments."},
            "p-gan": {"id": "p-gan", "label": "Paper", "title": "Generative Adversarial Nets", "name": "Generative Adversarial Nets", "year": 2014, "doi": "10.48550/arXiv.1406.2661", "abstract": "We propose a new framework for estimating generative models via an adversarial process, in which we simultaneously train two models: a generative model and a discriminative model."},
            "a-ashish-vaswani": {"id": "a-ashish-vaswani", "label": "Author", "name": "Ashish Vaswani"},
            "a-kaiming-he": {"id": "a-kaiming-he", "label": "Author", "name": "Kaiming He"},
            "a-thomas-kipf": {"id": "a-thomas-kipf", "label": "Author", "name": "Thomas Kipf"},
            "a-diederik-kingma": {"id": "a-diederik-kingma", "label": "Author", "name": "Diederik P. Kingma"},
            "a-ian-goodfellow": {"id": "a-ian-goodfellow", "label": "Author", "name": "Ian Goodfellow"},
            "inst-google": {"id": "inst-google", "label": "Institution", "name": "Google Research", "country": "United States"},
            "k-deep-learning": {"id": "k-deep-learning", "label": "Keyword", "name": "Deep Learning", "description": "A subset of machine learning based on artificial neural networks with representation learning.", "difficulty_level": "Beginner"},
            "k-nlp": {"id": "k-nlp", "label": "Keyword", "name": "Natural Language Processing", "description": "Interactions between computers and human languages, focusing on processing and analyzing large natural language data.", "difficulty_level": "Beginner"},
            "k-optimization": {"id": "k-optimization", "label": "Keyword", "name": "Optimization Algorithms", "description": "Methods used to minimize loss functions and train neural network models.", "difficulty_level": "Beginner"}
        }
        self.mock_edges = [
            # Prerequisite links
            {"from": "c-linear-algebra", "to": "c-matrix-operations", "type": "PREREQUISITE_OF"},
            {"from": "c-linear-algebra", "to": "c-gradient-descent", "type": "PREREQUISITE_OF"},
            {"from": "c-calculus", "to": "c-partial-derivatives", "type": "PREREQUISITE_OF"},
            {"from": "c-partial-derivatives", "to": "c-chain-rule", "type": "PREREQUISITE_OF"},
            {"from": "c-chain-rule", "to": "c-backpropagation", "type": "PREREQUISITE_OF"},
            {"from": "c-probability-stats", "to": "c-bayes-theorem", "type": "PREREQUISITE_OF"},
            {"from": "c-bayes-theorem", "to": "c-regularization", "type": "PREREQUISITE_OF"},
            {"from": "c-loss-function", "to": "c-gradient-descent", "type": "PREREQUISITE_OF"},
            {"from": "c-gradient-descent", "to": "c-sgd", "type": "PREREQUISITE_OF"},
            {"from": "c-gradient-descent", "to": "c-neural-networks", "type": "PREREQUISITE_OF"},
            {"from": "c-matrix-operations", "to": "c-neural-networks", "type": "PREREQUISITE_OF"},
            {"from": "c-neural-networks", "to": "c-activation-functions", "type": "PREREQUISITE_OF"},
            {"from": "c-activation-functions", "to": "c-sigmoid-relu", "type": "PREREQUISITE_OF"},
            {"from": "c-sigmoid-relu", "to": "c-feedforward-networks", "type": "PREREQUISITE_OF"},
            {"from": "c-backpropagation", "to": "c-feedforward-networks", "type": "PREREQUISITE_OF"},
            {"from": "c-feedforward-networks", "to": "c-cnns", "type": "PREREQUISITE_OF"},
            {"from": "c-feedforward-networks", "to": "c-rnns", "type": "PREREQUISITE_OF"},
            {"from": "c-rnns", "to": "c-lstms", "type": "PREREQUISITE_OF"},
            {"from": "c-lstms", "to": "c-seq2seq", "type": "PREREQUISITE_OF"},
            {"from": "c-seq2seq", "to": "c-attention", "type": "PREREQUISITE_OF"},
            {"from": "c-attention", "to": "c-self-attention", "type": "PREREQUISITE_OF"},
            {"from": "c-self-attention", "to": "c-multi-head-attention", "type": "PREREQUISITE_OF"},
            {"from": "c-multi-head-attention", "to": "c-transformers", "type": "PREREQUISITE_OF"},
            {"from": "c-positional-encoding", "to": "c-transformers", "type": "PREREQUISITE_OF"},
            {"from": "c-transformers", "to": "c-gnns", "type": "PREREQUISITE_OF"},
            {"from": "c-transformers", "to": "c-llms", "type": "PREREQUISITE_OF"},
            {"from": "c-gnns", "to": "c-gcns", "type": "PREREQUISITE_OF"},
            {"from": "c-llms", "to": "c-bert-gpt", "type": "PREREQUISITE_OF"},
            # Related/Extends
            {"from": "c-cnns", "to": "c-gnns", "type": "RELATED_TO"},
            {"from": "c-matrix-operations", "to": "c-partial-derivatives", "type": "RELATED_TO"},
            {"from": "c-sgd", "to": "c-optimization", "type": "RELATED_TO"},
            {"from": "c-backpropagation", "to": "c-regularization", "type": "RELATED_TO"},
            # Paper references to concepts
            {"from": "p-attention", "to": "c-transformers", "type": "USES_METHOD"},
            {"from": "p-resnet", "to": "c-cnns", "type": "USES_METHOD"},
            {"from": "p-gcn", "to": "c-gcns", "type": "USES_METHOD"},
            {"from": "p-adam", "to": "c-sgd", "type": "USES_METHOD"},
            {"from": "p-gan", "to": "c-neural-networks", "type": "USES_METHOD"},
            # Citations
            {"from": "p-gcn", "to": "p-attention", "type": "CITES"},
            # Authorship
            {"from": "p-attention", "to": "a-ashish-vaswani", "type": "AUTHORED_BY"},
            {"from": "p-resnet", "to": "a-kaiming-he", "type": "AUTHORED_BY"},
            {"from": "p-gcn", "to": "a-thomas-kipf", "type": "AUTHORED_BY"},
            {"from": "p-adam", "to": "a-diederik-kingma", "type": "AUTHORED_BY"},
            {"from": "p-gan", "to": "a-ian-goodfellow", "type": "AUTHORED_BY"},
            # Affiliation
            {"from": "a-ashish-vaswani", "to": "inst-google", "type": "AFFILIATED_WITH"},
            # Keywords
            {"from": "p-attention", "to": "k-deep-learning", "type": "HAS_KEYWORD"},
            {"from": "p-attention", "to": "k-nlp", "type": "HAS_KEYWORD"},
            {"from": "c-gradient-descent", "to": "k-optimization", "type": "HAS_KEYWORD"}
        ]
        # Dynamically set doc_id and create CONTAINS edges for doc-1
        for nid, node in list(self.mock_nodes.items()):
            node["session_id"] = None
            if nid != "doc-1":
                node["doc_id"] = "doc-1"
                self.mock_edges.append({
                    "from": "doc-1",
                    "to": nid,
                    "type": "CONTAINS"
                })

    def _run_mock_query(self, query: str, parameters: dict = None):
        query_upper = query.upper()
        params = parameters or {}

        if "RETURN 1" in query_upper:
            return [{"1": 1}]

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
            elif ":INSTITUTION" in query_upper:
                label = "Institution"
            
            name = params.get("name") or params.get("title") or "Node"
            node_id = params.get("id") or f"mock-n-{len(self.mock_nodes) + 1}"
            
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
                return [{"id": node["id"], "name": node["name"]} for node in self.mock_nodes.values() if node.get("label") == "Concept"]

            # Expand graph paths (Sprint 2 expand / traverse)
            if "PREREQUISITE_OF" in query_upper or "RELATED_TO" in query_upper or "EXTENDS" in query_upper or "PATH" in query_upper:
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

                if target_id in self.mock_nodes and target_id in doc_node_ids:
                    nodes_to_return[target_id] = self.mock_nodes[target_id]
                
                for edge in self.mock_edges:
                    if edge["type"] == "CONTAINS":
                        continue
                    if mode == "basic" and edge["type"] != "PREREQUISITE_OF":
                        continue
                    if session_id:
                        if edge.get("session_id") != session_id:
                            continue
                    elif doc_id and doc_id != "doc-1":
                        if edge.get("doc_id") != doc_id:
                            continue
                            
                    if edge["from"] in doc_node_ids and edge["to"] in doc_node_ids:
                        if edge["from"] == target_id or edge["to"] == target_id:
                            from_node = self.mock_nodes.get(edge["from"])
                            to_node = self.mock_nodes.get(edge["to"])
                            if from_node and to_node:
                                nodes_to_return[edge["from"]] = from_node
                                nodes_to_return[edge["to"]] = to_node
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
