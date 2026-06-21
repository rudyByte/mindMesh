import os
import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from api.routers import health, documents, graph, copilot, highlights, notes, citations, paths
from api.utils.neo4j_client import neo4j_client

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("main")

app = FastAPI(title="MindMesh API", version="1.0.0")

# Setup CORS to allow Next.js dev server access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(health.router, tags=["Health"])
app.include_router(documents.router, tags=["Documents"])
app.include_router(graph.router, tags=["Graph"])
app.include_router(copilot.router, tags=["Copilot"])
app.include_router(highlights.router, tags=["Highlights"])
app.include_router(notes.router, tags=["Notes"])
app.include_router(citations.router, tags=["Citations"])
app.include_router(paths.router, tags=["Paths"])

@app.on_event("startup")
def startup_event():
    logger.info("Starting up MindMesh API...")
    # Execute Neo4j constraints migration on start
    migration_path = os.path.join(os.path.dirname(__file__), "migrations", "001_constraints.cypher")
    if os.path.exists(migration_path):
        neo4j_client.execute_migration(migration_path)
    else:
        logger.warning(f"Migration file not found at {migration_path}")

@app.on_event("shutdown")
def shutdown_event():
    logger.info("Shutting down MindMesh API...")
    neo4j_client.close()
