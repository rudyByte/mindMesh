import asyncio
import logging
import sys
import os

# Adjust path so server modules can be imported
sys.path.append(os.path.abspath(os.path.dirname(__file__)))

from server.utils.llm_client import llm_client
from server.utils.neo4j_client import neo4j_client

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("test_pipeline")

def run_test():
    logger.info("Starting Ohm's Law Pipeline Test...")
    
    # 1. Provide mock text for Ohm's Law
    text = """
    Ohm's law states that the current through a conductor between two points is directly proportional to the voltage across the two points.
    Introducing the constant of proportionality, the resistance, one arrives at the usual mathematical equation that describes this relationship: I = V / R.
    An electric circuit is a path in which electrons from a voltage or current source flow.
    A voltmeter is an instrument used for measuring electrical potential difference between two points in an electric circuit.
    An ammeter is a measuring instrument used to measure the current in a circuit.
    """
    
    logger.info("--- STEP 1: Concept Extraction ---")
    res = llm_client.extract_graph_from_chunk(text)
    nodes = res.get("nodes", [])
    rels = res.get("relationships", [])
    
    logger.info(f"Extracted Nodes ({len(nodes)}):")
    for n in nodes:
        logger.info(f"  - {n.get('name')}")
        
    logger.info(f"Extracted Relationships ({len(rels)}):")
    for r in rels:
        logger.info(f"  - {r.get('from')} -[{r.get('type')}]-> {r.get('to')}")
        
    logger.info("--- STEP 2: Prerequisite Extraction Pass ---")
    concept_names = [n.get("name") for n in nodes if n.get("name")]
    prereqs = llm_client.extract_document_prerequisites(concept_names)
    
    logger.info(f"Generated PREREQUISITE relationships ({len(prereqs)}):")
    for r in prereqs:
        logger.info(f"  - {r.get('from')} -[PREREQUISITE]-> {r.get('to')}")
        
    logger.info("--- STEP 3: Neo4j Storage Verification ---")
    if not neo4j_client.is_mock():
        for p in prereqs:
            neo4j_client.run_query(
                "MERGE (a:Concept {id: $f, name: $f}) MERGE (b:Concept {id: $t, name: $t}) MERGE (a)-[:PREREQUISITE]->(b)",
                {"f": p.get("from"), "t": p.get("to")}
            )
            
    # Check counts
    node_count = neo4j_client.run_query("MATCH (n) RETURN count(n) as c")[0]['c'] if not neo4j_client.is_mock() else 0
    rel_count = neo4j_client.run_query("MATCH ()-[r]->() RETURN count(r) as c")[0]['c'] if not neo4j_client.is_mock() else 0
    prereq_count = neo4j_client.run_query("MATCH ()-[r:PREREQUISITE]->() RETURN count(r) as c")[0]['c'] if not neo4j_client.is_mock() else 0
    
    logger.info(f"Neo4j Total Nodes: {node_count}")
    logger.info(f"Neo4j Total Relationships: {rel_count}")
    logger.info(f"Neo4j PREREQUISITE Relationships: {prereq_count}")
    
    if not neo4j_client.is_mock():
        sample_rels = neo4j_client.run_query("MATCH (a)-[r:PREREQUISITE]->(b) RETURN a.name as a, type(r) as t, b.name as b LIMIT 50")
        for sr in sample_rels:
            logger.info(f"  Neo4j Stored: {sr['a']} -[{sr['t']}]-> {sr['b']}")
            
    logger.info("--- STEP 4: Roadmap Query Test ---")
    if prereqs:
        target_node = prereqs[-1].get("to")
        logger.info(f"Testing Roadmap Endpoint Logic for Target: {target_node}")
        
        roadmap_query = """
        MATCH path = (prereq)-[:PREREQUISITE*1..10]->(target {id: $node_id})
        WITH prereq, max(length(path)) AS max_depth
        ORDER BY max_depth DESC
        RETURN prereq.id AS id, labels(prereq)[0] AS label, coalesce(prereq.name, prereq.title, 'Unknown') AS name, coalesce(prereq.description, '') AS description
        """
        
        if not neo4j_client.is_mock():
            roadmap_res = neo4j_client.run_query(roadmap_query, {"node_id": target_node})
            logger.info(f"Roadmap query returned {len(roadmap_res)} concepts.")
            for rm in roadmap_res:
                logger.info(f"  - {rm}")
        else:
            logger.info("Skipping Cypher roadmap query test in mock mode.")

if __name__ == "__main__":
    run_test()
