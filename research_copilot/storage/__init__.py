"""
Research Copilot Storage Module

This module provides storage adapters for:
- Qdrant vector database
- Parent document store
- Research results cache
- Cloud Storage sync (for GCP deployment)
"""

from .qdrant_client import VectorDbManager
from .parent_store import ParentStoreManager
from .research_cache import ResearchCache
from .cloud_storage import (
    CloudStorageSync,
    initialize_cloud_storage_sync,
    sync_all_from_gcs,
    sync_all_to_gcs
)

__all__ = [
    "VectorDbManager",
    "ParentStoreManager",
    "ResearchCache",
    "CloudStorageSync",
    "initialize_cloud_storage_sync",
    "sync_all_from_gcs",
    "sync_all_to_gcs"
]
