"""
GCP-optimized configuration with Secret Manager support.
Falls back to environment variables for local development.

This module provides a hybrid approach:
- Local development: Uses environment variables (.env file)
- GCP production: Uses Google Secret Manager
- Environment variables can override secrets (useful for testing)
"""
import os
from typing import Optional
from functools import lru_cache

# Load environment variables from .env file (if present)
# This must happen before any os.getenv() calls
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    # python-dotenv not installed, skip .env loading
    pass

# Detect if running on GCP
def is_gcp_environment() -> bool:
    """Check if running on GCP."""
    return (
        os.getenv("GAE_ENV") is not None or  # App Engine
        os.getenv("K_SERVICE") is not None or  # Cloud Run
        os.getenv("GOOGLE_CLOUD_PROJECT") is not None  # Any GCP service
    )

def get_secret(secret_id: str, project_id: Optional[str] = None) -> Optional[str]:
    """
    Get secret from Google Secret Manager (production) or environment variable (local).
    
    Priority:
    1. Environment variable (highest priority - works everywhere)
    2. Secret Manager (if on GCP and env var not set)
    3. None (if neither available)
    
    Args:
        secret_id: Secret name in Secret Manager or env var name
        project_id: GCP project ID (auto-detected if None)
    
    Returns:
        Secret value or None if not found
    """
    # Try environment variable first (works locally and can override in Cloud Run)
    env_value = os.getenv(secret_id)
    if env_value:
        return env_value
    
    # If on GCP, try Secret Manager
    if is_gcp_environment():
        try:
            from google.cloud import secretmanager
            
            project_id = project_id or os.getenv("GOOGLE_CLOUD_PROJECT")
            if not project_id:
                print(f"⚠ Warning: GOOGLE_CLOUD_PROJECT not set, cannot fetch secret {secret_id}")
                return None
            
            client = secretmanager.SecretManagerServiceClient()
            name = f"projects/{project_id}/secrets/{secret_id}/versions/latest"
            
            response = client.access_secret_version(request={"name": name})
            secret_value = response.payload.data.decode("UTF-8")
            print(f"✓ Loaded secret {secret_id} from Secret Manager")
            return secret_value
        except ImportError:
            # google-cloud-secret-manager not installed (local dev)
            return None
        except Exception as e:
            # Secret not found or permission denied
            print(f"⚠ Warning: Could not fetch secret {secret_id} from Secret Manager: {e}")
            return None
    
    return None

# --- Directory Configuration ---
# Use /tmp on GCP (Cloud Run ephemeral storage), otherwise use local paths
if is_gcp_environment():
    MARKDOWN_DIR = os.getenv("MARKDOWN_DIR", "/tmp/markdown_docs")
    PARENT_STORE_PATH = os.getenv("PARENT_STORE_PATH", "/tmp/parent_store")
    QDRANT_DB_PATH = os.getenv("QDRANT_DB_PATH", "/tmp/qdrant_db")
else:
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
USE_NOTION_MCP = os.getenv("USE_NOTION_MCP", "false").lower() == "true"

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

# Notion MCP: default to npx-based server
_notion_mcp_cmd = os.getenv("NOTION_MCP_COMMAND", "npx,-y,@modelcontextprotocol/server-notion")
NOTION_MCP_COMMAND = _notion_mcp_cmd.split(",") if isinstance(_notion_mcp_cmd, str) else _notion_mcp_cmd
_notion_mcp_args = os.getenv("NOTION_MCP_ARGS", "")
NOTION_MCP_ARGS = _notion_mcp_args.split(",") if _notion_mcp_args else []

NOTION_PARENT_PAGE_ID = os.getenv("NOTION_PARENT_PAGE_ID")

# --- API Keys (from Secret Manager or env vars) ---
# Priority: Environment variable > Secret Manager > None
GOOGLE_API_KEY = get_secret("GOOGLE_API_KEY") or os.getenv("GOOGLE_API_KEY")
YOUTUBE_API_KEY = get_secret("YOUTUBE_API_KEY") or os.getenv("YOUTUBE_API_KEY")
GITHUB_TOKEN = get_secret("GITHUB_TOKEN") or os.getenv("GITHUB_TOKEN")
TAVILY_API_KEY = get_secret("TAVILY_API_KEY") or os.getenv("TAVILY_API_KEY")
NOTION_API_KEY = get_secret("NOTION_API_KEY") or os.getenv("NOTION_API_KEY")

# Log configuration source
if is_gcp_environment():
    print("✓ Running on GCP - using Secret Manager for API keys")
else:
    print("✓ Running locally - using environment variables for API keys")
