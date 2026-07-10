"""
Vercel Python ASGI entry point for MindMesh FastAPI backend.

Environment variables (set in Vercel dashboard):
  - NEO4J_URI / NEO4J_USER / NEO4J_PASSWORD : Neo4j Aura credentials
  - GROQ_API_KEY                             : Groq API key
  - GROQ_MODEL                               : Groq model name (optional)
  - SUPABASE_URL / SUPABASE_KEY              : Supabase project credentials
  - MULTI_DOCUMENT_MODE                      : "true" to enable multi-doc mode
"""
import sys
import os

# Add project root to sys.path so server/ package is importable
_project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from server.main import app

# Vercel Python runtime detects an ASGI app exported as `handler` or `app`.
handler = app
