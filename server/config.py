import os
from dotenv import load_dotenv, find_dotenv

# Search up to find the root .env file
load_dotenv(find_dotenv())

class Config:
    NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
    NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
    NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "password")

    ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
    ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-3-5-sonnet-20241022")

    SUPABASE_URL = os.getenv("SUPABASE_URL", "https://mock.supabase.co")
    SUPABASE_KEY = os.getenv("SUPABASE_KEY", "mock-anon-key")

    MULTI_DOCUMENT_MODE = os.getenv("MULTI_DOCUMENT_MODE", "false").lower() == "true"

config = Config()
