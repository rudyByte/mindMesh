import json
import logging
import re
from anthropic import Anthropic
from api.config import config

logger = logging.getLogger("llm_client")

GENERIC_BLACKLIST = {
    # Pronouns & basic structural words
    "something", "anything", "nothing", "someone", "anyone", "everyone", "nobody", "everybody",
    # Common conversational fillers/adverbs/adjectives
    "for example", "such as", "however", "therefore", "nevertheless", "furthermore", "consequently",
    "indeed", "instead", "meanwhile", "besides", "moreover", "otherwise", "similarly", "specifically",
    "especially", "particularly", "primarily", "secondly", "thirdly", "finally", "lastly",
    # Generic, non-domain nouns & terms
    "example", "examples", "case", "cases", "thing", "things", "part", "parts", "term", "terms",
    "concept", "concepts", "system", "systems", "approach", "approaches", "model", "models",
    "method", "methods", "methodology", "methodologies", "framework", "frameworks", "process", "processes",
    "technology", "technologies", "application", "applications", "data", "information", "detail", "details",
    "fact", "facts", "idea", "ideas", "knowledge", "structure", "structures", "problem", "problems",
    "solution", "solutions", "challenge", "challenges", "result", "results", "analysis", "analyses",
    "evaluation", "evaluations", "experiment", "experiments", "test", "tests", "performance", "performances",
    "comparison", "comparisons", "difference", "differences", "similarity", "similarities", "feature", "features",
    "property", "properties", "characteristic", "characteristics", "aspect", "aspects", "factor", "factors",
    "element", "elements", "component", "components", "object", "objects", "subject", "subjects",
    "user", "users", "client", "clients", "server", "servers", "network", "networks", "environment", "environments",
    "device", "devices", "resource", "resources", "tool", "tools", "way", "ways", "mode", "modes", "step", "steps",
    "phase", "phases", "stage", "stages", "level", "levels", "type", "types", "kind", "kinds", "class", "classes",
    "group", "groups", "set", "sets", "category", "categories", "section", "sections", "chapter", "chapters",
    "page", "pages", "figure", "figures", "table", "tables", "chart", "charts", "graph", "graphs", "diagram", "diagrams",
    "image", "images", "file", "files", "document", "documents", "paper", "papers", "article", "articles",
    "text", "texts", "book", "books", "note", "notes", "key", "keys", "value", "values", "right", "left",
    "extracting", "consistent", "consistency", "volume", "connectivity", "requirement", "requirements",
    "usage", "frequency", "power", "connectivity", "thing", "things", "internet", "world", "critical",
    "abstract", "introduction", "conclusion", "discussion", "references", "author", "title", "pdf", "ocr", "scanned"
}

def calculate_entity_quality(name: str, label: str) -> float:
    n_clean = name.strip()
    n_lower = n_clean.lower()
    
    # 1. Length checks
    if len(n_clean) <= 2:
        return 0.0  # too short
    if len(n_clean) >= 60:
        return 0.0  # too long (often a parsed phrase/sentence or formatting error)
        
    # 2. Blacklist / Generic check (both exact and substring matching for common phrases)
    if n_lower in GENERIC_BLACKLIST:
        return 0.0
        
    # Singularized check
    singular_n = n_lower
    if n_lower.endswith('s') and not n_lower.endswith('ss') and not n_lower.endswith('us') and not n_lower.endswith('is'):
        singular_n = n_lower[:-1]
    if singular_n in GENERIC_BLACKLIST:
        return 0.0
        
    # Check repeating words: e.g. "Data Data Data", "data data", "Test Test Test", repeated words
    if re.search(r'\b(\w{2,})\b(?:\s+\1\b)+', n_lower):
        return 0.0
        
    # Check repeating character sequences: e.g. "TESTTESTTEST", "abcabcabc"
    if re.search(r'(\w{3,})\1+', n_lower):
        return 0.0
        
    # Check placeholder/spam terms: e.g. "abc", "xyz", "qwe", "testtest", "dummy", "lorem", "ipsum"
    spam_terms = {"abc", "xyz", "qwe", "foo", "bar", "baz", "test", "testtest", "dummy", "lorem", "ipsum", "placeholder", "testtesttest", "spam", "garbage"}
    words_lower = n_lower.split()
    if any(w in spam_terms for w in words_lower) or any(t in n_lower for t in ["abc xyz", "xyz qwe", "abc xyz qwe", "testtest"]):
        return 0.0

    # Check mixed alphanumeric random strings without spaces (e.g. XYZ123XYZ, ABC99XYZ)
    if re.search(r'\b[a-zA-Z]+\d+[a-zA-Z]+\b', n_lower) or re.search(r'\b\d+[a-zA-Z]+\d+\b', n_lower):
        return 0.0

    # Check for random strings/gibberish (length >= 4 and no vowels at all, e.g. XYZ123XYZ has no vowels, qwrty has no vowels)
    for w in words_lower:
        if len(w) >= 4 and not any(v in w for v in 'aeiouy'):
            return 0.0

    # 3. Word count check: domain concepts are usually 1-4 words.
    words = n_clean.split()
    if len(words) > 4:
        # Deduct heavily for very long phrases (they are likely sentences/noise)
        return max(0.0, 1.0 - (len(words) - 4) * 0.25)
        
    # 4. OCR / Punctuation noise and layout artifacts
    special_chars = len(re.findall(r'[^a-zA-Z0-9\s-]', n_clean))
    if special_chars > 2:
        return 0.1
        
    # Check if it consists mostly of numbers or contains noise patterns
    if re.search(r'\d{3,}', n_clean):  # 3 or more digits (like page numbers, years, serials)
        return 0.2
    if re.match(r'^[_\-\d\s\W]+$', n_clean):  # only symbols/digits
        return 0.0
        
    # 5. Section headers (e.g. "Chapter 1", "Section A", "Figure 5", "Page 1")
    if re.match(r'^(chapter|section|figure|table|page|index|appendix|vol|volume|no|part|fig)\b', n_lower):
        return 0.0
        
    # 6. Common transitional phrases
    if any(n_lower.startswith(x) for x in ["for example", "such as", "based on", "due to", "in order to"]):
        return 0.1

    return 1.0

def singularize_concept_name(name: str) -> str:
    n = name.strip()
    n_lower = n.lower()
    
    # Plural rules
    if n_lower.endswith('ies'):
        return n[:-3] + 'y'
    elif n_lower.endswith('es') and not n_lower.endswith('see'):
        if n_lower.endswith('ices'):
            return n[:-4] + 'ex'
        return n[:-2]
    elif n_lower.endswith('s') and not n_lower.endswith('ss') and not n_lower.endswith('us') and not n_lower.endswith('is'):
        return n[:-1]
    return n

class LLMClient:
    def __init__(self):
        self._client = None
        self._is_mock = False
        
        if not config.ANTHROPIC_API_KEY or "mock-api-key" in config.ANTHROPIC_API_KEY:
            logger.warning("Default/mock Anthropic key detected. Starting LLM client in mock mode.")
            self._is_mock = True
            return
            
        try:
            self._client = Anthropic(api_key=config.ANTHROPIC_API_KEY)
            self._is_mock = False
            logger.info("Successfully connected to Anthropic Claude API.")
        except Exception as e:
            logger.warning(f"Failed to initialize Anthropic API client: {e}. Falling back to mock LLM mode.")
            self._is_mock = True

    def identify_main_topic(self, sample_text: str, filename: str) -> dict:
        if self._is_mock:
            return self._run_mock_main_topic(sample_text, filename)
            
        system_prompt = (
            "You are a main topic identification engine. Analyze the provided text sample from a document (and its filename) to identify the single primary topic/theme of the document. "
            "Return ONLY valid JSON matching this schema, no prose, no markdown fences:\n"
            "{\n"
            "  \"name\": \"Topic Name\",\n"
            "  \"description\": \"A short explanation of the topic/theme and its significance.\"\n"
            "}"
        )
        
        try:
            message = self._client.messages.create(
                model=config.ANTHROPIC_MODEL,
                max_tokens=1000,
                temperature=0,
                system=system_prompt,
                messages=[
                    {"role": "user", "content": f"Filename: {filename}\n\nText sample:\n\n{sample_text[:8000]}"}
                ]
            )
            content = message.content[0].text.strip()
            
            # Clean markdown JSON fences if LLM generated them
            if content.startswith("```json"):
                content = content[7:]
            if content.startswith("```"):
                content = content[3:]
            if content.endswith("```"):
                content = content[:-3]
            content = content.strip()
            
            data = json.loads(content)
            if "name" in data and "description" in data:
                return data
            raise ValueError("LLM returned JSON missing 'name' or 'description' keys.")
        except Exception as e:
            logger.error(f"Error during main topic identification: {e}")
            return self._run_mock_main_topic(sample_text, filename)

    def _run_mock_main_topic(self, sample_text: str, filename: str) -> dict:
        logger.info("[MOCK] Running mock main topic identification")
        sample_text_lower = sample_text.lower()
        filename_lower = filename.lower()
        
        if "attention" in sample_text_lower or "transformer" in sample_text_lower or "attention is all you need" in filename_lower:
            return {
                "name": "Transformer Architecture",
                "description": "A novel neural network architecture based solely on self-attention mechanisms, dispensing with recurrence and convolutions entirely."
            }
        elif "voting" in sample_text_lower or "blockchain" in sample_text_lower or "zkp" in sample_text_lower or "voting" in filename_lower:
            return {
                "name": "Secure Online Voting System",
                "description": "A secure, transparent, and tamper-proof online voting system using Blockchain that eliminates central administrator trust."
            }
        elif "knowledgeweb" in sample_text_lower or "blueprint" in filename_lower or "mindmprv" in filename_lower:
            return {
                "name": "KnowledgeWeb AI Architecture",
                "description": "GraphRAG-powered student prerequisite and citation mapping platform blueprint."
            }
            
        # Fallback
        clean_name = filename.rsplit('.', 1)[0].replace('_', ' ').replace('-', ' ').strip().title()
        if not clean_name:
            clean_name = "Document Analysis"
        return {
            "name": clean_name,
            "description": f"Unified knowledge map and conceptual analysis of the document {filename}."
        }

    def extract_graph_from_chunk(self, text_chunk: str) -> dict:
        if self._is_mock:
            return self._run_mock_extraction(text_chunk)
            
        system_prompt = (
            "You are a strict, grounded knowledge graph extraction engine. Given a text chunk, extract ONLY high-quality concepts, topics, papers, authors, or institutions that are EXPLICITLY mentioned. "
            "CRITICAL: Do NOT extract generic words (e.g., 'Data', 'System', 'Process', 'Approach', 'Model', 'Connectivity', 'Example'), conversational phrases (e.g., 'For Example', 'However', 'Therefore'), "
            "section headers ('Chapter 1', 'Section A'), page numbers, or formatting noise. Every extracted node must represent a meaningful domain-specific concept, technology, paper, or entity. "
            "For every extracted node, you MUST write a complete, rich, context-grounded description of at least 2-3 sentences based on the text. Avoid single-word or brief descriptions. "
            "Do NOT include any external knowledge or assumptions. "
            "Extract ONLY these node types: Concept, Topic, Keyword, Paper, Author, Institution. "
            "Extract ONLY these relationship types: PREREQUISITE_OF, RELATED_TO, EXTENDS, CONTRADICTS, USES_METHOD, DEPENDS_ON, CITES, AUTHORED_BY, AFFILIATED_WITH, MENTIONS, HAS_KEYWORD. "
            "Return ONLY valid JSON matching this schema, no prose, no markdown fences:\n"
            "{\n"
            "  \"nodes\": [\n"
            "    {\"label\": \"Concept\", \"name\": \"Linear Algebra\", \"description\": \"Linear algebra is the branch of mathematics concerning linear equations, linear functions, and their representations through matrices and vector spaces. It forms the mathematical foundation for machine learning algorithms like neural networks.\"}\n"
            "  ],\n"
            "  \"relationships\": [\n"
            "    {\"from\": \"Linear Algebra\", \"to\": \"Neural Networks\", \"type\": \"PREREQUISITE_OF\"}\n"
            "  ]\n"
            "}\n"
            "Strict grounding constraint: The extracted nodes and relationships MUST reside strictly within the bounds of the provided text. Do not invent concepts or reference external context not present in the text."
        )
        
        try:
            message = self._client.messages.create(
                model=config.ANTHROPIC_MODEL,
                max_tokens=4000,
                temperature=0,
                system=system_prompt,
                messages=[
                    {"role": "user", "content": f"Extract graph elements from this text chunk:\n\n{text_chunk}"}
                ]
            )
            content = message.content[0].text.strip()
            
            # Clean markdown JSON fences if LLM generated them
            if content.startswith("```json"):
                content = content[7:]
            if content.startswith("```"):
                content = content[3:]
            if content.endswith("```"):
                content = content[:-3]
            content = content.strip()
            
            data = json.loads(content)
            if "nodes" in data and "relationships" in data:
                return data
            raise ValueError("LLM returned JSON missing 'nodes' or 'relationships' keys.")
        except Exception as e:
            logger.error(f"Error during real LLM extraction: {e}")
            raise e

    def _run_mock_extraction(self, text_chunk: str) -> dict:
        logger.info("[MOCK] Running strictly grounded dynamic mock extraction on text chunk")
        
        text_chunk_lower = text_chunk.lower()
        if "noisy_pdf_trigger" in text_chunk_lower:
            logger.info("[MOCK] Returning noisy nodes to trigger the 20% validation failure.")
            nodes = [
                {"label": "Concept", "name": "Valid Concept One", "description": "This is a valid domain concept."},
                {"label": "Concept", "name": "Valid Concept Two", "description": "This is another valid domain concept."},
                {"label": "Concept", "name": "Lorem", "description": "Garbage entity."},
                {"label": "Concept", "name": "Page 1", "description": "Garbage entity."},
                {"label": "Concept", "name": "Test Test Test", "description": "Garbage entity."},
                {"label": "Concept", "name": "XYZ123XYZ", "description": "Garbage entity."},
            ]
            relationships = [
                {"from": "Valid Concept One", "to": "Valid Concept Two", "type": "RELATED_TO"}
            ]
            return {"nodes": nodes, "relationships": relationships}

        if "attention" in text_chunk_lower or "transformer" in text_chunk_lower or "encoder" in text_chunk_lower or "decoder" in text_chunk_lower:
            logger.info("[MOCK] Returning custom unified Transformer/Attention knowledge graph.")
            nodes = [
                {"label": "Topic", "name": "Transformer Architecture", "description": "A novel neural network architecture based solely on self-attention mechanisms, dispensing with recurrence and convolutions entirely."},
                {"label": "Concept", "name": "Encoder Stack", "description": "A stack of N=6 identical layers, each containing a multi-head self-attention mechanism and a position-wise feed-forward network."},
                {"label": "Concept", "name": "Decoder Stack", "description": "A stack of N=6 identical layers that includes self-attention, encoder-decoder attention, and feed-forward sub-layers."},
                {"label": "Concept", "name": "Scaled Dot-Product Attention", "description": "An attention function computing dot products of queries and keys, scaled by the square root of their dimension, followed by a softmax."},
                {"label": "Concept", "name": "Multi-Head Attention", "description": "An attention mechanism running several scaled dot-product attention layers in parallel over projected queries, keys, and values."},
                {"label": "Concept", "name": "Self-Attention", "description": "An attention mechanism relating different positions of a single sequence to compute a representation of the sequence."},
                {"label": "Concept", "name": "Encoder-Decoder Attention", "description": "A sub-layer in the decoder stack performing multi-head attention over the output of the encoder stack."},
                {"label": "Concept", "name": "Position-wise Feed-Forward Networks", "description": "Fully connected sub-layers applied to each position separately and identically in the encoder and decoder layers."},
                {"label": "Concept", "name": "Positional Encoding", "description": "Sinusoidal functions added to input embeddings to inject information about the relative or absolute positions of tokens."},
                {"label": "Concept", "name": "Learned Embeddings", "description": "Shared weight matrix embeddings mapping input and output tokens to continuous representation vectors of dimension d_model."},
                {"label": "Concept", "name": "Residual Connections", "description": "Additive skip connections around each sub-layer followed by layer normalization to facilitate deep gradient flow."},
                {"label": "Concept", "name": "Label Smoothing", "description": "A regularization technique introducing uncertainty during training to improve model generalization and BLEU score."},
                {"label": "Concept", "name": "Residual Dropout", "description": "Regularization applying dropout to sub-layer outputs and embedding sums to prevent overfitting."},
                {"label": "Concept", "name": "Adam Optimizer", "description": "Optimization algorithm utilizing adaptive estimates of lower-order moments with learning rate warmup."},
                {"label": "Concept", "name": "Sequence Transduction", "description": "The general task of mapping an input sequence of symbols to an output sequence of symbols, such as machine translation."},
                {"label": "Concept", "name": "BLEU Score", "description": "Bilingual Evaluation Understudy metric used to evaluate machine translation quality compared to human translations."},
                # Extracted Paper and Authors
                {"label": "Paper", "name": "Attention Is All You Need", "description": "The landmark paper introducing the Transformer architecture, replacing RNNs/CNNs with self-attention for sequence transduction tasks.", "year": 2017, "doi": "10.48550/arXiv.1706.03762"},
                {"label": "Author", "name": "Ashish Vaswani", "description": "Lead author of Attention Is All You Need and researcher at Google Brain."},
                {"label": "Author", "name": "Noam Shazeer", "description": "Co-author of Attention Is All You Need, known for key contributions to Transformer training scalability."},
                {"label": "Author", "name": "Niki Parmar", "description": "Co-author of Attention Is All You Need and AI researcher at Google Brain."},
                {"label": "Author", "name": "Jakob Uszkoreit", "description": "Co-author of Attention Is All You Need, senior software engineer and AI researcher."}
            ]
            relationships = [
                {"from": "Transformer Architecture", "to": "Encoder Stack", "type": "USES_METHOD"},
                {"from": "Transformer Architecture", "to": "Decoder Stack", "type": "USES_METHOD"},
                {"from": "Transformer Architecture", "to": "Self-Attention", "type": "USES_METHOD"},
                {"from": "Transformer Architecture", "to": "Positional Encoding", "type": "USES_METHOD"},
                {"from": "Transformer Architecture", "to": "Sequence Transduction", "type": "RELATED_TO"},
                {"from": "Transformer Architecture", "to": "Learned Embeddings", "type": "USES_METHOD"},
                {"from": "Transformer Architecture", "to": "Adam Optimizer", "type": "USES_METHOD"},
                {"from": "Transformer Architecture", "to": "Label Smoothing", "type": "USES_METHOD"},
                {"from": "Encoder Stack", "to": "Multi-Head Attention", "type": "USES_METHOD"},
                {"from": "Encoder Stack", "to": "Position-wise Feed-Forward Networks", "type": "USES_METHOD"},
                {"from": "Encoder Stack", "to": "Residual Connections", "type": "USES_METHOD"},
                {"from": "Decoder Stack", "to": "Multi-Head Attention", "type": "USES_METHOD"},
                {"from": "Decoder Stack", "to": "Encoder-Decoder Attention", "type": "USES_METHOD"},
                {"from": "Decoder Stack", "to": "Position-wise Feed-Forward Networks", "type": "USES_METHOD"},
                {"from": "Decoder Stack", "to": "Residual Connections", "type": "USES_METHOD"},
                {"from": "Multi-Head Attention", "to": "Scaled Dot-Product Attention", "type": "DEPENDS_ON"},
                {"from": "Multi-Head Attention", "to": "Self-Attention", "type": "RELATED_TO"},
                {"from": "Encoder-Decoder Attention", "to": "Encoder Stack", "type": "DEPENDS_ON"},
                {"from": "Encoder-Decoder Attention", "to": "Decoder Stack", "type": "DEPENDS_ON"},
                {"from": "Encoder-Decoder Attention", "to": "Multi-Head Attention", "type": "USES_METHOD"},
                {"from": "Positional Encoding", "to": "Learned Embeddings", "type": "RELATED_TO"},
                {"from": "Residual Connections", "to": "Residual Dropout", "type": "RELATED_TO"},
                {"from": "Label Smoothing", "to": "BLEU Score", "type": "RELATED_TO"},
                {"from": "Residual Dropout", "to": "BLEU Score", "type": "RELATED_TO"},
                {"from": "Adam Optimizer", "to": "BLEU Score", "type": "RELATED_TO"},
                # Paper & Author relationships
                {"from": "Attention Is All You Need", "to": "Ashish Vaswani", "type": "AUTHORED_BY"},
                {"from": "Attention Is All You Need", "to": "Noam Shazeer", "type": "AUTHORED_BY"},
                {"from": "Attention Is All You Need", "to": "Niki Parmar", "type": "AUTHORED_BY"},
                {"from": "Attention Is All You Need", "to": "Jakob Uszkoreit", "type": "AUTHORED_BY"},
                {"from": "Attention Is All You Need", "to": "Transformer Architecture", "type": "USES_METHOD"},
                {"from": "Attention Is All You Need", "to": "Self-Attention", "type": "USES_METHOD"}
            ]
            return {"nodes": nodes, "relationships": relationships}

        if "voting" in text_chunk_lower or "blockchain" in text_chunk_lower or "zkp" in text_chunk_lower or "blind signature" in text_chunk_lower:
            logger.info("[MOCK] Returning custom unified blockchain voting system knowledge graph.")
            nodes = [
                {"label": "Topic", "name": "Secure Online Voting System", "description": "A secure, transparent, and tamper-proof online voting system using Blockchain that eliminates central administrator trust."},
                {"label": "Concept", "name": "Zero-Knowledge Proofs", "description": "Cryptographic proofs enabling verification of voter eligibility without disclosing voter identity, preventing duplicate voting."},
                {"label": "Concept", "name": "Blind Signatures", "description": "Cryptographic signatures that validate the voting token without revealing voter identity, preventing voter-vote linkage."},
                {"label": "Concept", "name": "Commit-Reveal Mechanism", "description": "A two-phase voting protocol (commit and reveal) to prevent vote tampering during the active voting phase."},
                {"label": "Concept", "name": "Decentralized Identity", "description": "A privacy-preserving identity verification framework used for secure voter registration and authentication."},
                {"label": "Concept", "name": "Threshold Decryption", "description": "A decryption method requiring multiple key holders to collaborate, ensuring no single authority can access vote content."},
                {"label": "Concept", "name": "Zero-Trust Admin Architecture", "description": "A system design ensuring that administrators and key holders cannot view, modify, or link votes."},
                {"label": "Concept", "name": "Voter Application", "description": "The client-side interface where voters register, obtain anonymous tokens, and submit encrypted votes."},
                {"label": "Concept", "name": "Blockchain Network", "description": "The decentralized infrastructure providing an immutable ledger for vote hash storage and smart contract execution."},
                {"label": "Concept", "name": "Smart Contracts", "description": "Self-executing protocols on the blockchain that enforce voting rules and verify Zero-Knowledge Proofs automatically."},
                {"label": "Concept", "name": "IPFS", "description": "InterPlanetary File System used to store encrypted voting records in a secure, decentralized manner."},
                {"label": "Concept", "name": "Election Committee", "description": "A distributed set of key holders responsible for executing threshold decryption once voting has concluded."},
                {"label": "Keyword", "name": "Nullifier Hashes", "description": "Unique identifiers used to record that a vote has been cast, preventing duplicate voting without breaking anonymity."},
                {"label": "Concept", "name": "Trustless Governance", "description": "A governance framework operating transparently without relying on the integrity of a central party."},
                {"label": "Concept", "name": "Voter Anonymity", "description": "The complete separation of the voter's real identity from the cast ballot contents."}
            ]
            relationships = [
                {"from": "Secure Online Voting System", "to": "Zero-Knowledge Proofs", "type": "USES_METHOD"},
                {"from": "Secure Online Voting System", "to": "Blind Signatures", "type": "USES_METHOD"},
                {"from": "Secure Online Voting System", "to": "Commit-Reveal Mechanism", "type": "USES_METHOD"},
                {"from": "Secure Online Voting System", "to": "Decentralized Identity", "type": "USES_METHOD"},
                {"from": "Secure Online Voting System", "to": "Threshold Decryption", "type": "USES_METHOD"},
                {"from": "Secure Online Voting System", "to": "Zero-Trust Admin Architecture", "type": "USES_METHOD"},
                {"from": "Secure Online Voting System", "to": "Blockchain Network", "type": "DEPENDS_ON"},
                {"from": "Secure Online Voting System", "to": "Voter Application", "type": "DEPENDS_ON"},
                {"from": "Voter Application", "to": "Decentralized Identity", "type": "DEPENDS_ON"},
                {"from": "Voter Application", "to": "Blind Signatures", "type": "USES_METHOD"},
                {"from": "Blockchain Network", "to": "Smart Contracts", "type": "USES_METHOD"},
                {"from": "Blockchain Network", "to": "IPFS", "type": "USES_METHOD"},
                {"from": "Smart Contracts", "to": "Zero-Knowledge Proofs", "type": "USES_METHOD"},
                {"from": "Smart Contracts", "to": "Nullifier Hashes", "type": "USES_METHOD"},
                {"from": "Zero-Knowledge Proofs", "to": "Nullifier Hashes", "type": "RELATED_TO"},
                {"from": "Zero-Knowledge Proofs", "to": "Voter Anonymity", "type": "RELATED_TO"},
                {"from": "Blind Signatures", "to": "Voter Anonymity", "type": "RELATED_TO"},
                {"from": "Decentralized Identity", "to": "Voter Anonymity", "type": "RELATED_TO"},
                {"from": "Commit-Reveal Mechanism", "to": "IPFS", "type": "RELATED_TO"},
                {"from": "Threshold Decryption", "to": "Election Committee", "type": "DEPENDS_ON"},
                {"from": "Zero-Trust Admin Architecture", "to": "Threshold Decryption", "type": "RELATED_TO"},
                {"from": "Zero-Trust Admin Architecture", "to": "Trustless Governance", "type": "RELATED_TO"},
                {"from": "Blockchain Network", "to": "Trustless Governance", "type": "RELATED_TO"},
                {"from": "Voter Anonymity", "to": "Trustless Governance", "type": "RELATED_TO"},
                {"from": "Nullifier Hashes", "to": "Voter Anonymity", "type": "RELATED_TO"}
            ]
            return {"nodes": nodes, "relationships": relationships}

        STOP_WORDS = {
            "the", "a", "an", "in", "on", "at", "for", "to", "with", "by", "of", "and", "or", "but", 
            "this", "that", "these", "those", "it", "they", "we", "you", "he", "she", "as", "if", "when", 
            "is", "are", "was", "were", "been", "have", "has", "had", "do", "does", "did", "can", "could", 
            "should", "would", "will", "from", "through", "during", "before", "after", "under", "over", 
            "between", "among", "chapter", "section", "however", "therefore", "although", "furthermore",
            "thus", "so", "also", "then", "there", "their", "its", "our", "your", "my", "his", "her",
            "i", "you", "he", "him", "his", "himself", "she", "her", "hers", "herself", "itself", 
            "they", "them", "their", "theirs", "themselves", "what", "which", "who", "whom", "this", 
            "that", "these", "those", "am", "is", "are", "was", "were", "be", "been", "being", 
            "have", "has", "had", "having", "do", "does", "did", "doing", "a", "an", "the", "and", 
            "but", "if", "or", "because", "as", "until", "while", "of", "at", "by", "for", "with", 
            "about", "against", "between", "into", "through", "during", "before", "after", "above", 
            "below", "to", "from", "up", "down", "in", "out", "on", "off", "over", "under", "again", 
            "further", "then", "once"
        }

        nodes = []
        relationships = []
        
        # Split text chunk into sentences
        sentences = [s.strip() for s in re.split(r'(?<=[.!?])\s+|\n+', text_chunk) if s.strip()]
        
        concepts_map = {}
        
        # 1. Extract Capitalized Candidate Phrases
        for sent in sentences:
            # Find sequences of capitalized words
            matches = re.findall(r'\b([A-Z][a-zA-Z0-9\'-]*(?:\s+[A-Z][a-zA-Z0-9\'-]*)*)\b', sent)
            for phrase in matches:
                phrase_clean = phrase.strip()
                
                phrase_low = phrase_clean.lower()
                if phrase_low in STOP_WORDS or len(phrase_clean) < 3:
                    continue
                
                # Normalize name (singularize common plurals)
                normalized_name = singularize_concept_name(phrase_clean)
                normalized_low = normalized_name.lower()
                
                # Deduplicate and create candidate node
                if normalized_low not in concepts_map:
                    # Dynamically determine Label
                    label = "Concept"
                    if any(x in normalized_name for x in ["University", "Institute", "Research", "Lab", "Company", "Google", "Microsoft"]):
                        label = "Institution"
                    elif normalized_name.startswith("Chapter") or normalized_name.startswith("Section"):
                        label = "Topic"
                    
                    # Try to extract a definition from the sentence
                    description = ""
                    def_match = re.search(
                        rf"\b{re.escape(phrase_clean)}\b\s+(?:is\s+defined\s+as|refers\s+to|represents|denotes|means|is\s+an?|is|are|were|was)\s+([^.!?\n]{5,150})", 
                        sent, 
                        re.IGNORECASE
                    )
                    if def_match:
                        description = def_match.group(1).strip()
                        if description:
                            description = description[0].upper() + description[1:]
                    else:
                        # Fallback: clean the sentence containing the concept as description
                        description = sent
                        if len(description) > 150:
                            description = description[:147] + "..."
                            
                    concepts_map[normalized_low] = {
                        "label": label,
                        "name": normalized_name,
                        "description": description
                    }

        # Cap dynamic concept count to 15 per chunk to avoid rendering messy graphs
        sorted_concepts = list(concepts_map.values())[:15]
        nodes.extend(sorted_concepts)
        
        # Update concepts_map to only contain the kept concepts
        concepts_map = {n["name"].lower(): n for n in sorted_concepts}

        # 2. Extract Relationships
        for sent in sentences:
            sent_low = sent.lower()
            present_concepts = []
            for norm_name, node in concepts_map.items():
                if re.search(rf"\b{re.escape(node['name'])}\b", sent, re.IGNORECASE):
                    present_concepts.append(node['name'])
            
            if len(present_concepts) >= 2:
                # Link pairs of concepts present in the same sentence
                for i in range(len(present_concepts) - 1):
                    for j in range(i + 1, len(present_concepts)):
                        c1 = present_concepts[i]
                        c2 = present_concepts[j]
                        
                        c1_pos = sent_low.find(c1.lower())
                        c2_pos = sent_low.find(c2.lower())
                        
                        start_pos = min(c1_pos, c2_pos) + (len(c1) if c1_pos < c2_pos else len(c2))
                        end_pos = max(c1_pos, c2_pos)
                        between_text = sent_low[start_pos:end_pos]
                        
                        rel_type = "RELATED_TO"
                        if "depends" in between_text or "requires" in between_text or "built upon" in between_text:
                            if c1_pos < c2_pos:
                                relationships.append({"from": c2, "to": c1, "type": "PREREQUISITE_OF"})
                            else:
                                relationships.append({"from": c1, "to": c2, "type": "PREREQUISITE_OF"})
                        elif "prerequisite" in sent_low or "precedes" in between_text or "comes before" in between_text:
                            if c1_pos < c2_pos:
                                relationships.append({"from": c1, "to": c2, "type": "PREREQUISITE_OF"})
                            else:
                                relationships.append({"from": c2, "to": c1, "type": "PREREQUISITE_OF"})
                        elif "extends" in between_text or "generalizes" in between_text or "is a type of" in between_text:
                            if c1_pos < c2_pos:
                                relationships.append({"from": c1, "to": c2, "type": "EXTENDS"})
                            else:
                                relationships.append({"from": c2, "to": c1, "type": "EXTENDS"})
                        elif "contradicts" in between_text or "opposes" in between_text or "in contrast to" in between_text:
                            relationships.append({"from": c1, "to": c2, "type": "CONTRADICTS"})
                        elif "uses" in between_text or "utilizes" in between_text or "employs" in between_text:
                            if c1_pos < c2_pos:
                                relationships.append({"from": c2, "to": c1, "type": "USES_METHOD"})
                            else:
                                relationships.append({"from": c1, "to": c2, "type": "USES_METHOD"})
                        else:
                            relationships.append({"from": c1, "to": c2, "type": "RELATED_TO"})
                            
        # Ensure all extracted concepts in the chunk are connected in a chain or tree
        if len(sorted_concepts) > 1:
            for i in range(1, len(sorted_concepts)):
                c1 = sorted_concepts[i]["name"]
                c2 = sorted_concepts[0]["name"]  # Connect back to the first concept (hub)
                # Avoid duplicate relationship entries
                if not any((r["from"].lower() == c2.lower() and r["to"].lower() == c1.lower()) or (r["from"].lower() == c1.lower() and r["to"].lower() == c2.lower()) for r in relationships):
                    relationships.append({
                        "from": c2,
                        "to": c1,
                        "type": "RELATED_TO"
                    })
                            
        return {"nodes": nodes, "relationships": relationships}

    def narrate_learning_path(self, concepts: list) -> str:
        if self._is_mock:
            return self._run_mock_narration(concepts)
        
        concepts_str = " -> ".join([c for c in concepts])
        system_prompt = (
            "You are an encouraging academic AI tutor. Your task is to turn an ordered list of concepts "
            "representing a learning prerequisite path into a friendly, clear, step-by-step study plan. "
            "Write one short, helpful sentence per concept, explaining why it comes in this order and how "
            "it builds toward the final target concept. Keep the total response concise, direct, and under "
            "150 words in total."
        )
        try:
            message = self._client.messages.create(
                model=config.ANTHROPIC_MODEL,
                max_tokens=1000,
                temperature=0.5,
                system=system_prompt,
                messages=[
                    {"role": "user", "content": f"Please narrate this learning path: {concepts_str}"}
                ]
            )
            return message.content[0].text.strip()
        except Exception as e:
            logger.error(f"Error during path narration: {e}")
            return self._run_mock_narration(concepts)

    def _run_mock_narration(self, concepts: list) -> str:
        if not concepts:
            return "No prerequisite concepts found. You are ready to start with the target concept directly!"
        
        narration_steps = []
        for i, c in enumerate(concepts):
            if i == 0:
                narration_steps.append(f"First, build a solid foundation with **{c}**.")
            elif i == len(concepts) - 1:
                narration_steps.append(f"Finally, synthesize these tools to master the target concept **{c}**.")
            else:
                narration_steps.append(f"Next, transition into **{c}** to expand your understanding of relevant concepts.")
        
        return " ".join(narration_steps)

llm_client = LLMClient()
