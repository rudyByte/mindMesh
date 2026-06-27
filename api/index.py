"""
Vercel Python ASGI entry point for MindMesh FastAPI backend.

This file is the single serverless function that Vercel deploys.
It adds the `server/` directory to sys.path so that all existing
relative imports (e.g. `from routers import ...`, `from utils.xxx import ...`)
work without code changes.

Environment variables (set in Vercel dashboard):
  - NEO4J_URI / NEO4J_USER / NEO4J_PASSWORD : Neo4j Aura credentials
  - ANTHROPIC_API_KEY                        : Anthropic Claude API key
  - ANTHROPIC_MODEL                          : Claude model name (optional)
  - SUPABASE_URL / SUPABASE_KEY              : Supabase project credentials
  - MULTI_DOCUMENT_MODE                      : "true" to enable multi-doc mode
"""
import sys
import os

# Make the server/ directory importable so that existing absolute imports
# like `from routers import health` and `from utils.neo4j_client import neo4j_client` work.
_server_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "server")
if _server_dir not in sys.path:
    sys.path.insert(0, _server_dir)

from server.main import app

# Vercel Python runtime detects an ASGI app exported as `handler` or `app`.
handler = app
