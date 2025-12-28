"""
Configuration module for Research Copilot.

Supports both local development (environment variables) and GCP production (Secret Manager).

Usage:
    import config
    # All config values are available as config.GOOGLE_API_KEY, etc.
"""

# Load environment variables from .env file (if present)
# This must happen before importing gcp_settings which uses os.getenv()
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    # python-dotenv not installed, skip .env loading
    pass

# Import GCP settings (with Secret Manager support)
# This will automatically use Secret Manager on GCP and env vars locally
from config.gcp_settings import *
