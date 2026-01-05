"""
Configuration module for Research Copilot.

This file provides backward compatibility. For GCP deployment, use config/gcp_settings.py
which automatically uses Secret Manager in production and falls back to environment variables locally.
"""

# Load environment variables from .env file (if present)
# This must happen before any os.getenv() calls
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    # python-dotenv not installed, skip .env loading
    pass

# Try to import GCP settings (with Secret Manager support), fall back to basic config
try:
    from .gcp_settings import *
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
    LLM_MODEL = os.getenv("LLM_MODEL", "gemini-3.0-flash")
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
    
    # --- Tool-Specific Configuration ---
    MAX_ARXIV_RESULTS = int(os.getenv("MAX_ARXIV_RESULTS", "10"))
    MAX_CITATIONS_PER_AGENT = int(os.getenv("MAX_CITATIONS_PER_AGENT", "10"))
    
    # --- MCP Server Configuration ---
    USE_GITHUB_MCP = os.getenv("USE_GITHUB_MCP", "false").lower() == "true"
    USE_WEB_SEARCH_MCP = os.getenv("USE_WEB_SEARCH_MCP", "false").lower() == "true"
    
    # MCP server commands (local stdio transport)
    # GitHub MCP: default to npx-based server
    _github_mcp_cmd = os.getenv("GITHUB_MCP_COMMAND", "npx,-y,@modelcontextprotocol/server-github")
    GITHUB_MCP_COMMAND = _github_mcp_cmd.split(",") if isinstance(_github_mcp_cmd, str) else _github_mcp_cmd
    _github_mcp_args = os.getenv("GITHUB_MCP_ARGS", "")
    GITHUB_MCP_ARGS = _github_mcp_args.split(",") if _github_mcp_args else []
    
    # Web Search MCP: default to Python-based server (custom implementation)
    _web_mcp_cmd = os.getenv("WEB_SEARCH_MCP_COMMAND", "")
    WEB_SEARCH_MCP_COMMAND = _web_mcp_cmd.split(",") if _web_mcp_cmd else None  # None means use direct API
    _web_mcp_args = os.getenv("WEB_SEARCH_MCP_ARGS", "")
    WEB_SEARCH_MCP_ARGS = _web_mcp_args.split(",") if _web_mcp_args else []
    
    # Notion Configuration (Direct API only)
    NOTION_PARENT_PAGE_ID = os.getenv("NOTION_PARENT_PAGE_ID")
    
    # --- API Keys (from environment variables) ---
    GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
    YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY")
    GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
    TAVILY_API_KEY = os.getenv("TAVILY_API_KEY")
    NOTION_API_KEY = os.getenv("NOTION_API_KEY")
    
    _using_gcp_config = False
