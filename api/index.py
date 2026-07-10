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

try:
    import importlib
    from server.main import app as server_app
    
    # Mount all routes from server app into this app
    for route in server_app.routes:
        if hasattr(route, "methods") and hasattr(route, "path"):
            # Can't easily transfer routes, so just include the routers
            pass
    
    # Instead use include_router with all routers
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
except Exception as e:
    import traceback
    error_detail = traceback.format_exc()
    logger.error(f"Failed to load server routers: {e}\\{error_detail}")
    
    @app.get("/debug/import-error")
    def debug_import_error():
        return {"error": str(e), "traceback": error_detail}

@app.get("/health")
def get_health():
    return {"status": "ok"}

handler = app
