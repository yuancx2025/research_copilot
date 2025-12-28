from research_copilot.config import settings as config
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_qdrant import QdrantVectorStore, FastEmbedSparse, RetrievalMode
from qdrant_client import QdrantClient
from qdrant_client.http import models as qmodels
import os
import time

class VectorDbManager:
    __client: QdrantClient
    __dense_embeddings: HuggingFaceEmbeddings
    __sparse_embeddings: FastEmbedSparse
    def __init__(self):
        self.__client = QdrantClient(path=config.QDRANT_DB_PATH)
        
        # Set HF token from environment if available (for runtime downloads)
        hf_token = os.getenv("HF_TOKEN")
        if hf_token:
            os.environ["HF_TOKEN"] = hf_token
        
        # Initialize embeddings with retry logic for rate limit handling
        self.__dense_embeddings = self._init_embeddings_with_retry(config.DENSE_MODEL)
        self.__sparse_embeddings = FastEmbedSparse(model_name=config.SPARSE_MODEL)
    
    def _init_embeddings_with_retry(self, model_name, max_retries=5, base_delay=5):
        """Initialize embeddings with exponential backoff retry for rate limit handling."""
        for attempt in range(max_retries):
            try:
                if attempt == 0:
                    print(f"Loading embedding model: {model_name}")
                else:
                    print(f"Retrying model load: {model_name} (attempt {attempt + 1}/{max_retries})")
                
                embeddings = HuggingFaceEmbeddings(model_name=model_name)
                print(f"✓ Successfully loaded {model_name}")
                return embeddings
            except Exception as e:
                error_str = str(e)
                # Check for rate limit errors
                if "429" in error_str or "Too Many Requests" in error_str or "rate limit" in error_str.lower():
                    if attempt < max_retries - 1:
                        delay = base_delay * (2 ** attempt)  # Exponential backoff: 5s, 10s, 20s, 40s
                        print(f"⚠ Rate limited (429). Retrying in {delay} seconds...")
                        time.sleep(delay)
                    else:
                        print(f"❌ Failed to load model after {max_retries} attempts due to rate limiting")
                        print(f"   Error: {error_str}")
                        print(f"   Tip: Set HF_TOKEN environment variable for higher rate limits")
                        raise
                else:
                    # Non-rate-limit error, raise immediately
                    print(f"❌ Failed to load model: {error_str}")
                    raise
        return None

    def create_collection(self, collection_name):
        if not self.__client.collection_exists(collection_name):
            print(f"Creating collection: {collection_name}...")
            self.__client.create_collection(
                collection_name=collection_name,
                vectors_config=qmodels.VectorParams(size=len(self.__dense_embeddings.embed_query("test")), distance=qmodels.Distance.COSINE),
                sparse_vectors_config={config.SPARSE_VECTOR_NAME: qmodels.SparseVectorParams()},
            )
            print(f"✓ Collection created: {collection_name}")
        else:
            print(f"✓ Collection already exists: {collection_name}")

    def delete_collection(self, collection_name):
        try:
            if self.__client.collection_exists(collection_name):
                print(f"Removing existing Qdrant collection: {collection_name}")
                self.__client.delete_collection(collection_name)
        except Exception as e:
            print(f"Warning: could not delete collection {collection_name}: {e}")

    def get_collection(self, collection_name) -> QdrantVectorStore:
        try:
            return QdrantVectorStore(
                    client=self.__client,
                    collection_name=collection_name,
                    embedding=self.__dense_embeddings,
                    sparse_embedding=self.__sparse_embeddings,
                    retrieval_mode=RetrievalMode.HYBRID,
                    sparse_vector_name=config.SPARSE_VECTOR_NAME
                )
        except Exception as e:
            print(f"Unable to get collection {collection_name}: {e}")