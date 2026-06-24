import sys
import os

# Set Python path to find the 'api' directory and project root
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))) # api folder
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))) # project root

from api.routers.documents import are_semantically_similar, cluster_and_merge_nodes

def test_semantic_similarity():
    print("=== Testing Semantic Similarity ===")
    test_cases = [
        ("Attention", "Attention Mechanism", True),
        ("self-attention", "self attention mechanism", True),
        ("Neural Networks", "Neural Network", True),
        ("Deep Learning", "deep neural network", False),
        ("Calculus", "Vector Calculus", True), # "Calculus" is substring of "Vector Calculus"
        ("Zero Knowledge Proof", "Zero-Knowledge Proofs", True),
        ("IPFS", "InterPlanetary File System", False) # semantic is not string-match here
    ]
    
    all_passed = True
    for n1, n2, expected in test_cases:
        result = are_semantically_similar(n1, n2)
        passed = (result == expected)
        print(f"[{'PASS' if passed else 'FAIL'}] '{n1}' vs '{n2}': Expected={expected}, Got={result}")
        if not passed:
            all_passed = False
    return all_passed

def test_clustering_and_merging():
    print("\n=== Testing Clustering and Merging ===")
    dummy_nodes = [
        {"label": "Concept", "name": "Attention", "description": "Dynamic focus mechanism."},
        {"label": "Concept", "name": "Attention Mechanism", "description": "Focuses on specific input parts."},
        {"label": "Concept", "name": "Self-Attention", "description": "Attention relating different sequence positions."},
        {"label": "Concept", "name": "self attention mechanism", "description": "Computing representation of sequence."},
        {"label": "Concept", "name": "Neural Networks", "description": "Brain-inspired models."},
        {"label": "Concept", "name": "neural net", "description": "Artificial neural networks."},
        {"label": "Topic", "name": "Transformer Architecture", "description": "Main architecture."},
        {"label": "Keyword", "name": "ZKP", "description": "Zero knowledge."}
    ]
    
    canonical_nodes, name_mapping = cluster_and_merge_nodes(dummy_nodes)
    print("Merged Canonical Nodes:")
    for n in canonical_nodes:
        print(f"  - [{n['label']}] Name: '{n['name']}' | Description: '{n['description']}'")
        
    print("\nName Mapping:")
    for orig, canonical in name_mapping.items():
        print(f"  - '{orig}' -> '{canonical}'")
        
    # Verify duplicates merged
    attention_count = sum(1 for n in canonical_nodes if "attention" in n["name"].lower())
    # Attention and Attention Mechanism should be merged. Self-attention and self attention mechanism should be merged.
    # So we should have exactly 2 attention-related canonical nodes.
    print(f"Total attention canonical nodes: {attention_count} (Expected: 2)")
    
    nn_count = sum(1 for n in canonical_nodes if "neural" in n["name"].lower() or "net" in n["name"].lower())
    # Neural Networks and neural net should be merged (Expected: 1)
    print(f"Total neural net canonical nodes: {nn_count} (Expected: 1)")

    return attention_count == 2 and nn_count == 1

def test_graph_connectivity_logic():
    print("\n=== Testing Connected Component and Connection Logic ===")
    
    # We will simulate the component connection code directly to verify correctness
    central_node = {
        "label": "Topic",
        "name": "Transformer Architecture",
        "description": "A novel neural network architecture based solely on self-attention mechanisms."
    }
    
    canonical_nodes = [
        central_node,
        {"label": "Concept", "name": "Self-Attention", "description": "Attention mechanism."},
        {"label": "Concept", "name": "Positional Encoding", "description": "Inject relative position info."},
        {"label": "Concept", "name": "IPFS", "description": "Decentralized storage."},
        {"label": "Concept", "name": "Blockchain", "description": "Immutable ledger."}
    ]
    
    # Let's say we have the following relationships:
    # component 1 (connected to central): central -> Self-Attention
    # component 2: IPFS -> Blockchain
    # component 3 (isolated): Positional Encoding
    merged_relationships = [
        {"from": "Transformer Architecture", "to": "Self-Attention", "type": "USES_METHOD"},
        {"from": "IPFS", "to": "Blockchain", "type": "RELATED_TO"}
    ]
    
    nodes_by_name = {n["name"].lower().strip(): n for n in canonical_nodes}
    central_name_lower = central_node["name"].lower().strip()
    
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
            
    print("Identified Components:")
    for idx, comp in enumerate(components):
        print(f"  Component {idx + 1}: {comp}")
        
    central_comp_idx = -1
    for idx, comp in enumerate(components):
        if central_name_lower in comp:
            central_comp_idx = idx
            break
            
    print(f"Central component containing '{central_node['name']}' is index {central_comp_idx + 1}")
    
    final_relationships = list(merged_relationships)
    for idx, comp in enumerate(components):
        if idx == central_comp_idx:
            continue
        
        # Pick node in component (e.g. first one)
        target_node_name = comp[0]
        central_canonical_name = nodes_by_name[central_name_lower]["name"]
        target_canonical_name = nodes_by_name[target_node_name]["name"]
        
        final_relationships.append({
            "from": central_canonical_name,
            "to": target_canonical_name,
            "type": "RELATED_TO"
        })
        print(f"Connected component node '{target_canonical_name}' to central topic '{central_canonical_name}'")
        
    print("\nFinal Graph Relationships:")
    for r in final_relationships:
        print(f"  {r['from']} --({r['type']})--> {r['to']}")
        
    # Re-verify that after linking, the graph is fully connected
    # We rebuild adj with final_relationships
    adj_new = {name: set() for name in nodes_by_name.keys()}
    for r in final_relationships:
        f = r["from"].lower().strip()
        t = r["to"].lower().strip()
        if f in adj_new and t in adj_new:
            adj_new[f].add(t)
            adj_new[t].add(f)
            
    visited_new = set()
    queue = [central_name_lower]
    visited_new.add(central_name_lower)
    while queue:
        curr = queue.pop(0)
        for neighbor in adj_new[curr]:
            if neighbor not in visited_new:
                visited_new.add(neighbor)
                queue.append(neighbor)
                
    fully_connected = (len(visited_new) == len(canonical_nodes))
    print(f"\nIs the final graph fully connected? {fully_connected}")
    return fully_connected

if __name__ == "__main__":
    s1 = test_semantic_similarity()
    s2 = test_clustering_and_merging()
    s3 = test_graph_connectivity_logic()
    
    print("\n===============================")
    if s1 and s2 and s3:
        print("ALL TESTS PASSED SUCCESSFULLY!")
        sys.exit(0)
    else:
        print("SOME TESTS FAILED.")
        sys.exit(1)
