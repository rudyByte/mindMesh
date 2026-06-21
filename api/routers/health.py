from fastapi import APIRouter
from api.utils.neo4j_client import neo4j_client

router = APIRouter()

@router.get("/health")
def get_health():
    return {"status": "ok"}

@router.get("/graph/ping")
def get_graph_ping():
    is_ok = neo4j_client.ping()
    if is_ok:
        return {"status": "ok", "mode": "mock" if neo4j_client.is_mock() else "live"}
    return {"status": "fail"}
