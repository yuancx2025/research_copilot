"""
Configuration module for Research Copilot.

This file provides backward compatibility. For GCP deployment, use config/gcp_settings.py
which automatically uses Secret Manager in production and falls back to environment variables locally.
"""

# Try to import GCP settings (with Secret Manager support), fall back to basic config
try:
    from research_copilot.config.gcp_settings import *
    _using_gcp_config = True
except ImportError:
    # Fallback: Basic configuration using environment variables only
    import os
    
    # --- Directory Configuration ---
    MARKDOWN_DIR = os.getenv("MARKDOWN_DIR", "markdown_docs")
    PARENT_STORE_PATH = os.getenv("PARENT_STORE_PATH", "parent_store")
    QDRANT_DB_PATH = os.getenv("QDRANT_DB_PATH", "qdrant_db")
    
    # --- Qdrant Configuration ---
    CHILD_COLLECTION = os.getenv("CHILD_COLLECTION", "document_child_chunks")
    SPARSE_VECTOR_NAME = os.getenv("SPARSE_VECTOR_NAME", "sparse")
    
    # --- Model Configuration ---
    DENSE_MODEL = os.getenv("DENSE_MODEL", "sentence-transformers/all-mpnet-base-v2")
    SPARSE_MODEL = os.getenv("SPARSE_MODEL", "Qdrant/bm25")
    LLM_PROVIDER = os.getenv("LLM_PROVIDER", "google")
    LLM_MODEL = os.getenv("LLM_MODEL", "gemini-2.5-flash")
    LLM_TEMPERATURE = float(os.getenv("LLM_TEMPERATURE", "0"))
    
    # --- Text Splitter Configuration ---
    CHILD_CHUNK_SIZE = int(os.getenv("CHILD_CHUNK_SIZE", "500"))
    CHILD_CHUNK_OVERLAP = int(os.getenv("CHILD_CHUNK_OVERLAP", "100"))
    MIN_PARENT_SIZE = int(os.getenv("MIN_PARENT_SIZE", "2000"))
    MAX_PARENT_SIZE = int(os.getenv("MAX_PARENT_SIZE", "10000"))
    HEADERS_TO_SPLIT_ON = [
        ("#", "H1"),
        ("##", "H2"),
        ("###", "H3")
    ]
    
    # --- Reranking Configuration ---
    ENABLE_RERANKING = os.getenv("ENABLE_RERANKING", "true").lower() == "true"
    RERANK_TOP_K = int(os.getenv("RERANK_TOP_K", "5"))
    RERANK_INITIAL_K = int(os.getenv("RERANK_INITIAL_K", "20"))
    RERANK_BATCH_SIZE = int(os.getenv("RERANK_BATCH_SIZE", "5"))
    
    # --- Research Cache Configuration ---
    ENABLE_RESEARCH_CACHE = os.getenv("ENABLE_RESEARCH_CACHE", "true").lower() == "true"
    
    # --- MCP Server Configuration ---
    USE_GITHUB_MCP = os.getenv("USE_GITHUB_MCP", "false").lower() == "true"
    USE_WEB_SEARCH_MCP = os.getenv("USE_WEB_SEARCH_MCP", "false").lower() == "true"
    GITHUB_MCP_SERVER_URL = os.getenv("GITHUB_MCP_SERVER_URL")
    WEB_SEARCH_MCP_SERVER_URL = os.getenv("WEB_SEARCH_MCP_SERVER_URL")
    MCP_SERVER_AUTH_TOKEN = os.getenv("MCP_SERVER_AUTH_TOKEN")
    MCP_CONNECTION_TIMEOUT = int(os.getenv("MCP_CONNECTION_TIMEOUT", "30"))
    
    # --- API Keys (from environment variables) ---
    GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
    YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY")
    GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
    TAVILY_API_KEY = os.getenv("TAVILY_API_KEY")
    
    _using_gcp_config = False
