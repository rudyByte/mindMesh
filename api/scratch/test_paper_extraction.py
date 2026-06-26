import sys
import os

# Set Python path to find the 'api' directory and project root
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))) # api folder
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))) # project root

from api.utils.llm_client import LLMClient

def test_static_mock_extraction_counts_and_types():
    # We use a known trigger for static mock extraction
    text = "transformer architecture attention mechanism"
    client = LLMClient()
    res = client._run_mock_extraction(text)
    nodes, edges = res["nodes"], res["relationships"]
    
    assert len(nodes) >= 30, f"Expected at least 30 nodes for rich static graph, got {len(nodes)}"
    
    # Check for presence of Method and Dataset labels
    labels = {n.get("label") for n in nodes}
    assert "Method" in labels, "Expected 'Method' label in nodes"
    assert "Dataset" in labels, "Expected 'Dataset' label in nodes"
    
    # Check relationship types
    edge_types = {e.get("type") for e in edges}
    assert "USES" in edge_types or "USED_FOR" in edge_types or "EVALUATED_ON" in edge_types, "Expected rich relationship types"

def test_dynamic_mock_extraction():
    # Use a dynamic sentence
    text = "We evaluated the ResNet Method on the ImageNet Dataset."
    client = LLMClient()
    res = client._run_mock_extraction(text)
    nodes, edges = res["nodes"], res["relationships"]
    
    labels = {n.get("label") for n in nodes}
    assert "Method" in labels, "Expected 'Method' from dynamic extraction"
    assert "Dataset" in labels, "Expected 'Dataset' from dynamic extraction"
    
    edge_types = {e.get("type") for e in edges}
    assert "EVALUATED_ON" in edge_types or "RELATED_TO" in edge_types or "USES" in edge_types, f"Got edge types: {edge_types}"
