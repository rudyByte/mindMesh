"""
Vercel Python ASGI entry point for MindMesh FastAPI backend.
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="MindMesh API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Try to import and mount the full server app
import sys
import os
import logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("api")

_project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

_server_error = None
_server_traceback = None

try:
    from server.routers import health, documents, graph, copilot, highlights, notes, citations, paths
    app.include_router(health.router, tags=["Health"])
    app.include_router(documents.router, tags=["Documents"])
    app.include_router(graph.router, tags=["Graph"])
    app.include_router(copilot.router, tags=["Copilot"])
    app.include_router(highlights.router, tags=["Highlights"])
    app.include_router(notes.router, tags=["Notes"])
    app.include_router(citations.router, tags=["Citations"])
    app.include_router(paths.router, tags=["Paths"])
    logger.info("Successfully loaded server routers")
except Exception as _e:
    import traceback
    _server_error = str(_e)
    _server_traceback = traceback.format_exc()
    logger.error(f"Failed to load server routers: {_server_error}\\n{_server_traceback}")

@app.get("/debug/import-error")
def debug_import_error():
    if _server_error:
        return {"error": _server_error, "traceback": _server_traceback}
    return {"message": "No import error - server loaded successfully"}

@app.get("/health")
def get_health():
    return {"status": "ok"}

handler = app
