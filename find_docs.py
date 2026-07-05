from typing import Optional
from server.utils.neo4j_client import neo4j_client

# Find Automata documents
query = "MATCH (d:Document) RETURN d.id as doc_id, d.title as title"
res = neo4j_client.run_query(query)

print("All docs:", res)

# Find Automata doc
automata_docs = [d for d in res if "Automata" in d.get("title", "")]
if not automata_docs:
    print("No Automata documents found")
    
    # Try finding in Paper
    query = "MATCH (p:Paper) RETURN p.id as doc_id, p.doc_id as real_doc_id, p.title as title"
    papers = neo4j_client.run_query(query)
    
    automata_papers = [p for p in papers if "Automata" in p.get("title", "")]
    print("Automata papers:", automata_papers)
    
    if automata_papers:
        for p in automata_papers:
            real_doc_id: Optional[str] = p.get("real_doc_id")
            if real_doc_id:
                print("Found real_doc_id:", real_doc_id)
else:
    print("Found Automata docs:", automata_docs)
