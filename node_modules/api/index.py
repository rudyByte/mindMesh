"""
Vercel Python ASGI entry point for MindMesh FastAPI backend.
"""
import sys
import os
import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("mindmesh")

# Ensure project root is importable so server/ package can be found
_project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

app = FastAPI(title="MindMesh API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount all server routers
from server.routers import health, documents, graph, copilot, highlights, notes, citations, paths

app.include_router(health.router, tags=["Health"])
app.include_router(documents.router, tags=["Documents"])
app.include_router(graph.router, tags=["Graph"])
app.include_router(copilot.router, tags=["Copilot"])
app.include_router(highlights.router, tags=["Highlights"])
app.include_router(notes.router, tags=["Notes"])
app.include_router(citations.router, tags=["Citations"])
app.include_router(paths.router, tags=["Paths"])

logger.info("MindMesh API fully loaded")

handler = app
