import atexit
import os
from langchain_core.language_models import BaseChatModel
from research_copilot.config import settings as config
from research_copilot.config.defaults import DEFAULT_LLM_MODEL, DEFAULT_OLLAMA_MODEL
from research_copilot.storage.qdrant_client import VectorDbManager
from research_copilot.storage.parent_store import ParentStoreManager
from research_copilot.storage.research_cache import ResearchCache
from research_copilot.rag.chunker import Chunker
from research_copilot.rag.reranker import Reranker
from research_copilot.rag.retriever import Retriever
from research_copilot.core.source_setup import build_source_registry
from research_copilot.runtime.source_registry import SourceContext
from research_copilot.orchestrator.graph import create_agent_graph
from research_copilot.storage.cloud_storage import (
    initialize_cloud_storage_sync,
    sync_all_from_gcs,
    sync_all_to_gcs
)

_SHARED_RATE_LIMITER = None


def shared_rate_limiter():
    """One process-wide limiter from LLM_REQUESTS_PER_MINUTE, shared by every model we create.

    Free-tier quotas are per project, so the research model and the reranker
    must draw from the same budget.
    """
    global _SHARED_RATE_LIMITER
    rpm = float(os.getenv("LLM_REQUESTS_PER_MINUTE", "0") or 0)
    if rpm <= 0:
        return None
    if _SHARED_RATE_LIMITER is None:
        from langchain_core.rate_limiters import InMemoryRateLimiter
        from research_copilot.evals.tracing import MeasuredRateLimiter
        # Measured so run traces report provider latency without our own throttling wait.
        _SHARED_RATE_LIMITER = MeasuredRateLimiter(InMemoryRateLimiter(
            requests_per_second=rpm / 60, check_every_n_seconds=0.1, max_bucket_size=1))
    return _SHARED_RATE_LIMITER


def create_llm(rate_limiter=None) -> BaseChatModel:
    """Create LLM instance based on configured provider.

    ``rate_limiter`` overrides the shared LLM_REQUESTS_PER_MINUTE limiter.
    """
    rate_limiter = rate_limiter or shared_rate_limiter()
    provider = getattr(config, 'LLM_PROVIDER', 'ollama').lower()
    
    if provider == 'google':
        from langchain_google_genai import ChatGoogleGenerativeAI
        
        api_key = getattr(config, 'GOOGLE_API_KEY', None)
        if not api_key:
            raise ValueError(
                "GOOGLE_API_KEY not set. Please set it as environment variable "
                "or in config.py. Get your key from: https://makersuite.google.com/app/apikey"
            )
        
        model_name = getattr(config, 'LLM_MODEL', None) or DEFAULT_LLM_MODEL
        temperature = getattr(config, 'LLM_TEMPERATURE', 0)
        
        print(f"✓ Using Google Gemini API: {model_name}")
        return ChatGoogleGenerativeAI(
            model=model_name,
            temperature=temperature,
            google_api_key=api_key,
            rate_limiter=rate_limiter,
        )
    else:
        from langchain_ollama import ChatOllama
        model_name = getattr(config, 'LLM_MODEL', None) or DEFAULT_OLLAMA_MODEL
        temperature = getattr(config, 'LLM_TEMPERATURE', 0)
        print(f"✓ Using Ollama: {model_name}")
        return ChatOllama(model=model_name, temperature=temperature, rate_limiter=rate_limiter)

class RAGSystem:
    
    def __init__(self, collection_name=config.CHILD_COLLECTION):
        self.collection_name = collection_name
        self.vector_db = VectorDbManager()
        self.parent_store = ParentStoreManager()
        self.chunker = Chunker()
        self.agent_graph = None
        self.checkpointer = None
        self.tool_registry = None
        self.reranker = None
        self.retriever = None
        self.research_cache = None
        self.gcs_sync = None
        
    def _source_context(self, notion_service=None):
        extras = {}
        if notion_service:
            extras["notion_service"] = notion_service
        return SourceContext(
            llm=self.llm,
            config=config,
            collection=self.collection,
            retriever=self.retriever,
            extras=extras,
        )

    def initialize(self, checkpointer=None):
        self.checkpointer = checkpointer
        self.gcs_sync = initialize_cloud_storage_sync()
        if self.gcs_sync:
            sync_all_from_gcs(
                config.QDRANT_DB_PATH,
                config.PARENT_STORE_PATH,
                config.MARKDOWN_DIR,
                self.gcs_sync
            )
            atexit.register(
                sync_all_to_gcs,
                config.QDRANT_DB_PATH,
                config.PARENT_STORE_PATH,
                config.MARKDOWN_DIR,
                self.gcs_sync
            )
        self.vector_db.create_collection(self.collection_name)
        collection = self.vector_db.get_collection(self.collection_name)
        
        llm = create_llm()
        self.llm = llm
        self.collection = collection
        self.notion_service = None
        self._graph_generation = None
        self._mcp_prepared = False
        
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
        
        self.retriever = Retriever(
            collection=collection,
            parent_store=self.parent_store,
            reranker=self.reranker,
            enable_reranking=config.ENABLE_RERANKING and self.reranker is not None
        )
        
        if config.ENABLE_RESEARCH_CACHE:
            self.research_cache = ResearchCache()
            print("✓ Research cache initialized")
        
        self.tool_registry = build_source_registry()
        self.tool_registry.ensure_toolkits(self._source_context())
        self.agent_graph = create_agent_graph(
            llm, config, collection, research_cache=self.research_cache,
            tool_registry=self.tool_registry, retriever=self.retriever,
            checkpointer=self.checkpointer,
        )
    
    async def prepare_run(self, notion_service=None):
        """Initialize tools and rebuild only when the connection generation changes."""
        if not self._mcp_prepared:
            await self.tool_registry.initialize_mcp()
        generation = notion_service.connection.generation if notion_service and notion_service.connection.connected else None
        if generation:
            try:
                await notion_service.prepare()
            except Exception:
                generation = None
        if not self._mcp_prepared or generation != self._graph_generation:
            self.agent_graph = create_agent_graph(
                self.llm, config, self.collection,
                research_cache=self.research_cache, tool_registry=self.tool_registry,
                notion_service=notion_service if generation else None,
                retriever=self.retriever, checkpointer=self.checkpointer,
            )
            self._graph_generation = generation
            self._mcp_prepared = True
        self.notion_service = notion_service

    def invalidate_graph(self):
        """Drop connection-bound tools; saved conversation threads live in the checkpointer."""
        self._mcp_prepared = False
        self.agent_graph = None
        self._graph_generation = None
