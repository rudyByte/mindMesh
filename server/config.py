import os
from dotenv import load_dotenv, find_dotenv

# Search up to find the root .env file
load_dotenv(find_dotenv())

class Config:
    NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
    NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
    NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "password")

    # Groq (primary LLM provider)
    GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
    GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
    GROQ_BASE_URL = os.getenv("GROQ_BASE_URL", "https://api.groq.com/openai/v1")
    LLM_TIMEOUT_SECONDS = float(os.getenv("LLM_TIMEOUT_SECONDS", "20"))
    SERVERLESS_LOCAL_EXTRACTION = os.getenv("SERVERLESS_LOCAL_EXTRACTION", "true").lower() == "true"

    # Anthropic (legacy fallback — use GROQ_API_KEY for new deployments)
    ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
    ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-3-5-sonnet-20241022")

    # Embeddings for entity resolution
    EMBEDDING_PROVIDER = os.getenv("EMBEDDING_PROVIDER", "local").lower()
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
    EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")
    EMBEDDING_SIMILARITY_THRESHOLD = float(os.getenv("EMBEDDING_SIMILARITY_THRESHOLD", "0.97"))

    SUPABASE_URL = os.getenv("SUPABASE_URL", "https://mock.supabase.co")
    SUPABASE_KEY = os.getenv("SUPABASE_KEY", "mock-anon-key")

    MULTI_DOCUMENT_MODE = os.getenv("MULTI_DOCUMENT_MODE", "false").lower() == "true"

config = Config()
