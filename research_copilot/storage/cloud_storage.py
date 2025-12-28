"""
Cloud Storage integration for persistent data storage on GCP.

This module provides utilities to sync local data directories (Qdrant DB,
parent store, markdown docs) with Google Cloud Storage buckets.
"""
import os
import shutil
from pathlib import Path
from typing import Optional
from google.cloud import storage
from google.cloud.exceptions import NotFound


def is_gcp_environment() -> bool:
    """Check if running on GCP."""
    return (
        os.getenv("GAE_ENV") is not None or  # App Engine
        os.getenv("K_SERVICE") is not None or  # Cloud Run
        os.getenv("GOOGLE_CLOUD_PROJECT") is not None  # Any GCP service
    )


class CloudStorageSync:
    """Manages synchronization between local directories and Cloud Storage."""
    
    def __init__(self, bucket_name: Optional[str] = None):
        """
        Initialize Cloud Storage sync.
        
        Args:
            bucket_name: GCS bucket name. If None, reads from GCS_BUCKET_NAME env var.
        """
        self.bucket_name = bucket_name or os.getenv("GCS_BUCKET_NAME")
        if not self.bucket_name:
            raise ValueError(
                "GCS_BUCKET_NAME not set. Set it as environment variable "
                "or pass bucket_name parameter."
            )
        
        # Initialize GCS client (works with default credentials on GCP)
        try:
            self.client = storage.Client()
            self.bucket = self.client.bucket(self.bucket_name)
            print(f"✓ Connected to Cloud Storage bucket: {self.bucket_name}")
        except Exception as e:
            print(f"⚠ Warning: Could not initialize Cloud Storage client: {e}")
            print("  This is OK if running locally without GCP credentials.")
            self.client = None
            self.bucket = None
    
    def sync_from_gcs(self, local_path: str, gcs_prefix: str) -> bool:
        """
        Download data from Cloud Storage to local directory.
        
        Args:
            local_path: Local directory path to sync to
            gcs_prefix: GCS prefix (directory path) to sync from
            
        Returns:
            True if sync successful, False otherwise
        """
        if not self.bucket:
            print(f"⚠ Cloud Storage not available, skipping sync from {gcs_prefix}")
            return False
        
        local_dir = Path(local_path)
        local_dir.mkdir(parents=True, exist_ok=True)
        
        try:
            # List all blobs with the prefix
            blobs = list(self.bucket.list_blobs(prefix=gcs_prefix))
            
            if not blobs:
                print(f"  No existing data found in gs://{self.bucket_name}/{gcs_prefix}")
                return True
            
            print(f"  Downloading {len(blobs)} files from gs://{self.bucket_name}/{gcs_prefix}...")
            
            downloaded = 0
            for blob in blobs:
                # Get relative path from prefix
                relative_path = blob.name[len(gcs_prefix):].lstrip("/")
                if not relative_path:  # Skip if it's just the prefix itself
                    continue
                
                local_file = local_dir / relative_path
                local_file.parent.mkdir(parents=True, exist_ok=True)
                
                # Download blob
                blob.download_to_filename(str(local_file))
                downloaded += 1
            
            print(f"  ✓ Downloaded {downloaded} files to {local_path}")
            return True
            
        except NotFound:
            print(f"  Bucket {self.bucket_name} not found, starting fresh")
            return True
        except Exception as e:
            print(f"  ⚠ Error syncing from Cloud Storage: {e}")
            return False
    
    def sync_to_gcs(self, local_path: str, gcs_prefix: str) -> bool:
        """
        Upload data from local directory to Cloud Storage.
        
        Args:
            local_path: Local directory path to sync from
            gcs_prefix: GCS prefix (directory path) to sync to
            
        Returns:
            True if sync successful, False otherwise
        """
        if not self.bucket:
            print(f"⚠ Cloud Storage not available, skipping sync to {gcs_prefix}")
            return False
        
        local_dir = Path(local_path)
        if not local_dir.exists():
            print(f"  Local directory {local_path} does not exist, nothing to sync")
            return True
        
        try:
            # Ensure prefix ends with /
            if not gcs_prefix.endswith("/"):
                gcs_prefix += "/"
            
            # Upload all files recursively
            uploaded = 0
            for local_file in local_dir.rglob("*"):
                if local_file.is_file():
                    # Get relative path from local_dir
                    relative_path = local_file.relative_to(local_dir)
                    blob_name = gcs_prefix + str(relative_path).replace("\\", "/")
                    
                    # Upload file
                    blob = self.bucket.blob(blob_name)
                    blob.upload_from_filename(str(local_file))
                    uploaded += 1
            
            if uploaded > 0:
                print(f"  ✓ Uploaded {uploaded} files to gs://{self.bucket_name}/{gcs_prefix}")
            else:
                print(f"  No files to upload from {local_path}")
            
            return True
            
        except Exception as e:
            print(f"  ⚠ Error syncing to Cloud Storage: {e}")
            return False
    
    def sync_qdrant_db(self, local_path: str) -> bool:
        """Sync Qdrant database directory."""
        return self.sync_from_gcs(local_path, "qdrant_db/")
    
    def sync_qdrant_db_to_gcs(self, local_path: str) -> bool:
        """Sync Qdrant database directory to GCS."""
        return self.sync_to_gcs(local_path, "qdrant_db/")
    
    def sync_parent_store(self, local_path: str) -> bool:
        """Sync parent store directory."""
        return self.sync_from_gcs(local_path, "parent_store/")
    
    def sync_parent_store_to_gcs(self, local_path: str) -> bool:
        """Sync parent store directory to GCS."""
        return self.sync_to_gcs(local_path, "parent_store/")
    
    def sync_markdown_docs(self, local_path: str) -> bool:
        """Sync markdown docs directory."""
        return self.sync_from_gcs(local_path, "markdown_docs/")
    
    def sync_markdown_docs_to_gcs(self, local_path: str) -> bool:
        """Sync markdown docs directory to GCS."""
        return self.sync_to_gcs(local_path, "markdown_docs/")


def initialize_cloud_storage_sync() -> Optional[CloudStorageSync]:
    """
    Initialize Cloud Storage sync if running on GCP.
    
    Returns:
        CloudStorageSync instance if on GCP and configured, None otherwise
    """
    if not is_gcp_environment():
        print("✓ Running locally - Cloud Storage sync disabled")
        return None
    
    bucket_name = os.getenv("GCS_BUCKET_NAME")
    if not bucket_name:
        print("⚠ GCS_BUCKET_NAME not set - Cloud Storage sync disabled")
        return None
    
    try:
        return CloudStorageSync(bucket_name)
    except Exception as e:
        print(f"⚠ Could not initialize Cloud Storage sync: {e}")
        return None


def sync_all_from_gcs(
    qdrant_path: str,
    parent_store_path: str,
    markdown_dir: str,
    gcs_sync: Optional[CloudStorageSync] = None
) -> bool:
    """
    Sync all data directories from Cloud Storage on startup.
    
    Args:
        qdrant_path: Local Qdrant DB path
        parent_store_path: Local parent store path
        markdown_dir: Local markdown docs directory
        gcs_sync: CloudStorageSync instance (will create if None)
    
    Returns:
        True if all syncs successful
    """
    if gcs_sync is None:
        gcs_sync = initialize_cloud_storage_sync()
        if gcs_sync is None:
            return False
    
    print("🔄 Syncing data from Cloud Storage...")
    success = True
    success &= gcs_sync.sync_qdrant_db(qdrant_path)
    success &= gcs_sync.sync_parent_store(parent_store_path)
    success &= gcs_sync.sync_markdown_docs(markdown_dir)
    
    if success:
        print("✓ Data sync from Cloud Storage complete")
    else:
        print("⚠ Some data syncs failed, continuing anyway...")
    
    return success


def sync_all_to_gcs(
    qdrant_path: str,
    parent_store_path: str,
    markdown_dir: str,
    gcs_sync: Optional[CloudStorageSync] = None
) -> bool:
    """
    Sync all data directories to Cloud Storage on shutdown.
    
    Args:
        qdrant_path: Local Qdrant DB path
        parent_store_path: Local parent store path
        markdown_dir: Local markdown docs directory
        gcs_sync: CloudStorageSync instance (will create if None)
    
    Returns:
        True if all syncs successful
    """
    if gcs_sync is None:
        gcs_sync = initialize_cloud_storage_sync()
        if gcs_sync is None:
            return False
    
    print("🔄 Syncing data to Cloud Storage...")
    success = True
    success &= gcs_sync.sync_qdrant_db_to_gcs(qdrant_path)
    success &= gcs_sync.sync_parent_store_to_gcs(parent_store_path)
    success &= gcs_sync.sync_markdown_docs_to_gcs(markdown_dir)
    
    if success:
        print("✓ Data sync to Cloud Storage complete")
    else:
        print("⚠ Some data syncs failed")
    
    return success

