import re

def is_valid_concept_name(name: str) -> bool:
    name_clean = name.strip()
    if not name_clean or len(name_clean) < 3 or len(name_clean) > 60:
        return False
    
    # Check if first word is a common instruction verb
    first_word = name_clean.split()[0].lower().rstrip(',.:')
    action_verbs = {
        "go", "click", "run", "download", "install", "open", "verify", "check", 
        "select", "choose", "make", "create", "use", "see", "read", "write", 
        "review", "complete", "exit", "login", "sign", "upload", "submit", 
        "configure", "set", "setup", "please", "remember", "ensure", "avoid"
    }
    if first_word in action_verbs:
        return False
        
    if len(name_clean.split()) > 7:
        return False
        
    return True

def clean_concept_name(name: str) -> str:
    # Remove markdown formatting like bold/italics
    name_clean = re.sub(r'[*_`]', '', name).strip().rstrip(',.;:-')
    if not name_clean:
        return ""
    # Capitalize first letter if it is lowercase
    if name_clean[0].islower():
        name_clean = name_clean[0].upper() + name_clean[1:]
    return name_clean

def parse_learning_sequences(text: str) -> tuple[list[dict], list[dict]]:
    nodes = []
    relationships = []
    
    lines = [line.strip() for line in text.split('\n')]
    
    # 1. Match Phase / Step / Section sequence declarations line by line
    phase_regex = re.compile(
        r"^\s*(?:\#+\s+|-\s+|\*\s+|\d+\.\s+)?\b(Phase|Step|Section)\s+(\d+(?:\.\d+)*)\s*[:.-]?\s*([^\n.!?]{2,60})",
        re.IGNORECASE
    )
    
    sequences = {}
    for line in lines:
        match = phase_regex.search(line)
        if match:
            prefix_type = match.group(1).title()
            seq_num = match.group(2)
            concept_name = match.group(3).strip()
            
            concept_name = clean_concept_name(concept_name)
            if is_valid_concept_name(concept_name):
                if prefix_type not in sequences:
                    sequences[prefix_type] = []
                sequences[prefix_type].append((seq_num, concept_name))
                
    # Process Phase/Step/Section sequences
    for prefix_type, items in sequences.items():
        def parse_seq_num(val):
            try:
                parts = val.split('.')
                return [float(p) for p in parts]
            except Exception:
                return [0.0]
                
        items_sorted = sorted(items, key=lambda x: parse_seq_num(x[0]))
        
        if len(items_sorted) >= 2:
            print(f"Detected {prefix_type} sequence of length {len(items_sorted)}:")
            for seq_num, name in items_sorted:
                print(f"  - {seq_num}: {name}")
                nodes.append({
                    "label": "Concept",
                    "name": name,
                    "description": f"{prefix_type} {seq_num} of the study sequence: {name}."
                })
            for i in range(len(items_sorted) - 1):
                relationships.append({
                    "from": items_sorted[i][1],
                    "to": items_sorted[i+1][1],
                    "type": "PREREQUISITE_OF"
                })

    # 2. Match numbered lists line by line
    list_regex = re.compile(r"^\s*(?:\#+\s+)?(\d+)\.\s*([^\n.!?]{2,60})")
    
    current_sequence = []
    last_num = None
    
    def save_current_sequence():
        nonlocal nodes, relationships
        if len(current_sequence) >= 2:
            valid_items = [clean_concept_name(item[1]) for item in current_sequence if is_valid_concept_name(clean_concept_name(item[1]))]
            if len(valid_items) >= 2:
                print(f"Detected sequential list of length {len(valid_items)}:")
                for i, item_name in enumerate(valid_items):
                    print(f"  - {i+1}. {item_name}")
                    nodes.append({
                        "label": "Concept",
                        "name": item_name,
                        "description": f"Found in sequential list: {item_name}."
                    })
                for i in range(len(valid_items) - 1):
                    relationships.append({
                        "from": valid_items[i],
                        "to": valid_items[i+1],
                        "type": "PREREQUISITE_OF"
                    })
                    
    for line in lines:
        match = list_regex.match(line)
        if match:
            num = int(match.group(1))
            name = match.group(2).strip()
            
            if num == 1:
                save_current_sequence()
                current_sequence = [(num, name)]
                last_num = 1
            elif last_num is not None and num == last_num + 1:
                current_sequence.append((num, name))
                last_num = num
            else:
                save_current_sequence()
                current_sequence = []
                last_num = None
        else:
            if line.startswith("- ") or line.startswith("* "):
                save_current_sequence()
                current_sequence = []
                last_num = None
                
    save_current_sequence()

    # 3. Match arrow prerequisite sequences
    for line in lines:
        if "->" in line or "→" in line:
            parts = re.split(r"->|→", line)
            cleaned_parts = [clean_concept_name(p) for p in parts]
            valid_parts = [p for p in cleaned_parts if is_valid_concept_name(p)]
            
            if len(valid_parts) >= 2:
                print(f"Detected arrow sequence: {' -> '.join(valid_parts)}")
                for p in valid_parts:
                    nodes.append({
                        "label": "Concept",
                        "name": p,
                        "description": f"Extracted from prerequisite sequence: {p}."
                    })
                for i in range(len(valid_parts) - 1):
                    relationships.append({
                        "from": valid_parts[i],
                        "to": valid_parts[i+1],
                        "type": "PREREQUISITE_OF"
                    })
                    
    # Deduplicate nodes by lowercase name
    unique_nodes = []
    seen_nodes = set()
    for n in nodes:
        name_low = n["name"].lower()
        if name_low not in seen_nodes:
            seen_nodes.add(name_low)
            unique_nodes.append(n)
            
    # Deduplicate relationships
    unique_rels = []
    seen_rels = set()
    for r in relationships:
        key = (r["from"].lower(), r["to"].lower(), r["type"])
        if r["from"].lower() != r["to"].lower() and key not in seen_rels:
            seen_rels.add(key)
            unique_rels.append(r)
            
    return unique_nodes, unique_rels

# Test text
sample_doc_text = """
Welcome to the course.
Phase 1: Zero-Knowledge Proofs
We start with Phase 1, which introduces cryptographic verification without revealing secret information.
Phase 2: Zero-Trust Admin Access
In Phase 2, we implement decentralization so that administrators cannot compromise voter privacy.
Phase 3: zero-knowledge voting
Finally, Phase 3 integrates ZKP and zero-trust admin into a fully secure voting system.

Another document layout:
1. Deep Learning Basics
2. Neural Network Optimization
3. Large Language Model Training

Arrow sequence:
Linear Algebra -> Matrix Operations -> Neural Networks -> Transformers -> BERT & GPT
"""

nodes, rels = parse_learning_sequences(sample_doc_text)
print(f"\nFinal Extracted Nodes count: {len(nodes)}")
print(f"Final Extracted Relationships count: {len(rels)}")
print(f"Rels: {rels}")

