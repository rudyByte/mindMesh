import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from api.utils.neo4j_client import neo4j_client

# Simulate Document insertion
query_insert = """
MERGE (d:Document {id: $id})
ON CREATE SET d.title = $title, d.type = 'pdf', d.upload_date = $upload_date, 
              d.storage_url = $storage_url, d.status = 'processing', d.progress_pct = 10
RETURN d
"""

params_insert = {
    'id': '80f2ac0b-f800-4b3b-bb21-37c9bc1f1920',
    'title': 'CarbonGuard ppt (1).pdf',
    'upload_date': '2026-06-21T21:47:46.580216',
    'storage_url': 'file:///C:/Users/HARASIDDHI/OneDrive/Desktop/MindMesh/mock_storage/documents/80f2ac0b-f800-4b3b-bb21-37c9bc1f1920_CarbonGuard ppt (1).pdf'
}

print("Running insert query...")
res_insert = neo4j_client.run_query(query_insert, params_insert)
print("Insert result:", res_insert)
print("Mock nodes keys:", list(neo4j_client.mock_nodes.keys()))
print("Mock node data for doc:", neo4j_client.mock_nodes.get('80f2ac0b-f800-4b3b-bb21-37c9bc1f1920'))

# Simulate Match query
query_match = "MATCH (d:Document {id: $id}) RETURN d.title as title, d.storage_url as url"
params_match = {'id': '80f2ac0b-f800-4b3b-bb21-37c9bc1f1920'}

print("\nRunning match query...")
res_match = neo4j_client.run_query(query_match, params_match)
print("Match result:", res_match)
