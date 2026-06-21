import json
import logging
import re
from anthropic import Anthropic
from api.config import config

logger = logging.getLogger("llm_client")

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

    def extract_graph_from_chunk(self, text_chunk: str) -> dict:
        if self._is_mock:
            return self._run_mock_extraction(text_chunk)
            
        system_prompt = (
            "You are a knowledge graph extraction engine. Given a text chunk, extract ONLY these node types: "
            "Concept, Topic, Keyword, Paper, Author, Institution. Extract ONLY these relationship types: "
            "PREREQUISITE_OF, RELATED_TO, EXTENDS, CONTRADICTS, USES_METHOD, DEPENDS_ON, CITES, AUTHORED_BY, "
            "AFFILIATED_WITH, MENTIONS, HAS_KEYWORD. Return ONLY valid JSON matching this schema, no prose, "
            "no markdown fences:\n"
            "{\n"
            "  \"nodes\": [\n"
            "    {\"label\": \"Concept\", \"name\": \"Linear Algebra\", \"description\": \"Study of vectors and matrices.\"}\n"
            "  ],\n"
            "  \"relationships\": [\n"
            "    {\"from\": \"Linear Algebra\", \"to\": \"Neural Networks\", \"type\": \"PREREQUISITE_OF\"}\n"
            "  ]\n"
            "}\n"
            "If the text is a research paper excerpt, prioritize Paper/Author/Citation extraction. If it is "
            "educational/textbook content, prioritize Concept/Topic extraction with PREREQUISITE_OF relationships "
            "reflecting genuine learning dependency order."
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
        logger.info("[MOCK] Running mock extraction on text chunk")
        
        nodes = []
        relationships = []
        chunk_lower = text_chunk.lower()
        
        has_attention = "attention" in chunk_lower or "query" in chunk_lower or "key" in chunk_lower
        has_transformers = "transformer" in chunk_lower or "attention" in chunk_lower or "attention is all you need" in chunk_lower
        has_neural_net = "neural network" in chunk_lower or "neuron" in chunk_lower or "backpropagation" in chunk_lower
        has_gradient = "gradient" in chunk_lower or "optimization" in chunk_lower or "descent" in chunk_lower
        has_linear_algebra = "matrix" in chunk_lower or "vector" in chunk_lower or "linear" in chunk_lower
        
        if has_attention or has_transformers:
            nodes.append({"label": "Concept", "name": "Transformers", "description": "Deep learning model architecture using self-attention."})
            nodes.append({"label": "Concept", "name": "Self-attention", "description": "An attention mechanism scaling connections within a single sequence."})
            nodes.append({"label": "Concept", "name": "Deep Learning", "description": "Multi-layered neural network representation learning."})
            relationships.append({"from": "Self-attention", "to": "Transformers", "type": "PREREQUISITE_OF"})
            relationships.append({"from": "Deep Learning", "to": "Transformers", "type": "RELATED_TO"})
            
        if has_neural_net:
            nodes.append({"label": "Concept", "name": "Neural Networks", "description": "Layered computational graph nodes resembling biological neurons."})
            nodes.append({"label": "Concept", "name": "Backpropagation", "description": "Reverse pass chain rule gradients computation."})
            relationships.append({"from": "Backpropagation", "to": "Neural Networks", "type": "USES_METHOD"})
            
        if has_gradient:
            nodes.append({"label": "Concept", "name": "Gradient Descent", "description": "First-order optimization to minimize loss function parameters."})
            nodes.append({"label": "Concept", "name": "Loss Function", "description": "Error quantification metric for output matching."})
            relationships.append({"from": "Gradient Descent", "to": "Neural Networks", "type": "PREREQUISITE_OF"})
            
        if has_linear_algebra:
            nodes.append({"label": "Concept", "name": "Linear Algebra", "description": "Math studying systems of equations, spaces, vectors, and matrices."})
            relationships.append({"from": "Linear Algebra", "to": "Gradient Descent", "type": "PREREQUISITE_OF"})
            
        if not nodes:
            nodes.append({"label": "Concept", "name": "Artificial Intelligence", "description": "Machine-based cognitive simulation."})
            nodes.append({"label": "Concept", "name": "Machine Learning", "description": "Experience-driven statistical algorithms optimization."})
            relationships.append({"from": "Machine Learning", "to": "Artificial Intelligence", "type": "PREREQUISITE_OF"})

        return {"nodes": nodes, "relationships": relationships}

llm_client = LLMClient()
