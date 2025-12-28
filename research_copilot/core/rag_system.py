import uuid
import atexit
from langchain_core.language_models import BaseChatModel
from research_copilot.config import settings as config
from research_copilot.storage.qdrant_client import VectorDbManager
from research_copilot.storage.parent_store import ParentStoreManager
from research_copilot.storage.research_cache import ResearchCache
from research_copilot.rag.chunker import Chunker
from research_copilot.rag.reranker import Reranker
from research_copilot.rag.retriever import Retriever
from research_copilot.tools.registry import initialize_registry
from research_copilot.tools.base import SourceType
from research_copilot.orchestrator.graph import create_agent_graph
from research_copilot.storage.cloud_storage import (
    initialize_cloud_storage_sync,
    sync_all_from_gcs,
    sync_all_to_gcs
)

def create_llm() -> BaseChatModel:
    """Create LLM instance based on configured provider."""
    provider = getattr(config, 'LLM_PROVIDER', 'ollama').lower()
    
    if provider == 'google':
        from langchain_google_genai import ChatGoogleGenerativeAI
        
        api_key = getattr(config, 'GOOGLE_API_KEY', None)
        if not api_key:
            raise ValueError(
                "GOOGLE_API_KEY not set. Please set it as environment variable "
                "or in config.py. Get your key from: https://makersuite.google.com/app/apikey"
            )
        
        model_name = getattr(config, 'LLM_MODEL', 'gemini-pro')
        temperature = getattr(config, 'LLM_TEMPERATURE', 0)
        
        print(f"✓ Using Google Gemini API: {model_name}")
        return ChatGoogleGenerativeAI(
            model=model_name,
            temperature=temperature,
            google_api_key=api_key
        )
    else:
        # Default to Ollama
        from langchain_ollama import ChatOllama
        model_name = getattr(config, 'LLM_MODEL', 'qwen3:4b-instruct-2507-q4_K_M')
        temperature = getattr(config, 'LLM_TEMPERATURE', 0)
        print(f"✓ Using Ollama: {model_name}")
        return ChatOllama(model=model_name, temperature=temperature)

class RAGSystem:
    
    def __init__(self, collection_name=config.CHILD_COLLECTION):
        self.collection_name = collection_name
        self.vector_db = VectorDbManager()
        self.parent_store = ParentStoreManager()
        self.chunker = Chunker()
        self.agent_graph = None
        self.thread_id = str(uuid.uuid4())
        self.tool_registry = None
        self.reranker = None
        self.retriever = None
        self.research_cache = None
        self.gcs_sync = None
        
    def initialize(self):
        # Sync from Cloud Storage on startup (if on GCP)
        self.gcs_sync = initialize_cloud_storage_sync()
        if self.gcs_sync:
            sync_all_from_gcs(
                config.QDRANT_DB_PATH,
                config.PARENT_STORE_PATH,
                config.MARKDOWN_DIR,
                self.gcs_sync
            )
            # Register shutdown handler to sync to GCS
            atexit.register(
                sync_all_to_gcs,
                config.QDRANT_DB_PATH,
                config.PARENT_STORE_PATH,
                config.MARKDOWN_DIR,
                self.gcs_sync
            )
        self.vector_db.create_collection(self.collection_name)
        collection = self.vector_db.get_collection(self.collection_name)
        
        # Create LLM instance using the helper function
        llm = create_llm()
        
        # Initialize LLM for reranking if enabled
        if config.ENABLE_RERANKING:
            try:
                reranker_llm = create_llm()
                self.reranker = Reranker(
                    llm=reranker_llm,
                    top_k=config.RERANK_TOP_K,
                    batch_size=getattr(config, 'RERANK_BATCH_SIZE', 5)
                )
                if self.reranker.is_available():
                    print("✓ LLM-based reranker initialized")
                else:
                    print("⚠ Reranker not available, reranking disabled")
                    self.reranker = None
            except Exception as e:
                print(f"⚠ Warning: Failed to initialize reranker: {e}")
                self.reranker = None
        
        # Initialize retriever with reranker
        self.retriever = Retriever(
            collection=collection,
            parent_store=self.parent_store,
            reranker=self.reranker,
            enable_reranking=config.ENABLE_RERANKING and self.reranker is not None
        )
        
        # Initialize research cache if enabled
        if config.ENABLE_RESEARCH_CACHE:
            self.research_cache = ResearchCache()
            print("✓ Research cache initialized")
        
        # Initialize tool registry with config
        self.tool_registry = initialize_registry(config)
        
        # Set collection for local toolkit (needs collection for document search)
        local_toolkit = self.tool_registry.get_toolkit(SourceType.LOCAL)
        if local_toolkit:
            local_toolkit.set_collection(collection)
            # Also set retriever if local toolkit supports it
            if hasattr(local_toolkit, 'set_retriever'):
                local_toolkit.set_retriever(self.retriever)
        
        # Create orchestrator graph with multi-agent routing
        # Pass research cache if available
        self.agent_graph = create_agent_graph(llm, config, collection, research_cache=self.research_cache)
    
    def get_config(self):
        return {"configurable": {"thread_id": self.thread_id}}
    
    def reset_thread(self):
        try:
            self.agent_graph.checkpointer.delete_thread(self.thread_id)
        except Exception as e:
            print(f"Warning: Could not delete thread {self.thread_id}: {e}")
        self.thread_id = str(uuid.uuid4())