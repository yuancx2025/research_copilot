"""
Configuration module for Research Copilot.

Supports both local development (environment variables) and GCP production (Secret Manager).

Usage:
    import config
    # All config values are available as config.GOOGLE_API_KEY, etc.
"""

# Import GCP settings (with Secret Manager support)
# This will automatically use Secret Manager on GCP and env vars locally
from config.gcp_settings import *
