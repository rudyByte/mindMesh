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

@router.get("/health/deep")
def get_deep_health():
    from api.utils.supabase_client import supabase_client
    from api.utils.llm_client import llm_client
    from api.config import config
    
    # 1. Neo4j Status
    try:
        neo4j_ok = neo4j_client.ping()
        neo4j_mode = "mock" if neo4j_client.is_mock() else "live"
        neo4j_status = {"status": "ok" if neo4j_ok else "error", "mode": neo4j_mode}
    except Exception as e:
        neo4j_status = {"status": "error", "message": str(e)}

    # 2. Supabase Status
    try:
        if supabase_client._is_mock:
            supabase_status = {"status": "ok", "mode": "mock"}
        else:
            # list_buckets is a simple request that verifies keys/URL are correct
            supabase_client._client.storage.list_buckets()
            supabase_status = {"status": "ok", "mode": "live"}
    except Exception as e:
        supabase_status = {"status": "error", "message": str(e)}

    # 3. Anthropic API Status
    try:
        if llm_client._is_mock:
            anthropic_status = {"status": "ok", "mode": "mock"}
        else:
            # Request a single token to verify keys/network connection
            llm_client._client.messages.create(
                model=config.ANTHROPIC_MODEL,
                max_tokens=1,
                messages=[{"role": "user", "content": "ping"}]
            )
            anthropic_status = {"status": "ok", "mode": "live"}
    except Exception as e:
        anthropic_status = {"status": "error", "message": str(e)}

    overall_ok = (
        neo4j_status["status"] == "ok" and 
        supabase_status["status"] == "ok" and 
        anthropic_status["status"] == "ok"
    )

    return {
        "status": "ok" if overall_ok else "error",
        "services": {
            "neo4j": neo4j_status,
            "supabase": supabase_status,
            "anthropic": anthropic_status
        }
    }
