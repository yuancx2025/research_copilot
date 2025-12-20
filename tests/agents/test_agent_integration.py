"""
Integration tests for agents with real LLM and APIs.

These tests execute agents with real LLM calls and API requests.
Run with: pytest tests/test_agent_integration.py -v -m integration

Requirements:
- Real LLM (Ollama configured in config.py)
- API keys (optional for most sources)
- Set environment variables:
  - GITHUB_TOKEN (optional)
  - YOUTUBE_API_KEY (optional)
  - TAVILY_API_KEY (optional)
"""
import pytest
import os
import uuid
from unittest.mock import Mock
import config

# Try to import LLM providers
try:
    from langchain_google_genai import ChatGoogleGenerativeAI
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False

try:
    from langchain_ollama import ChatOllama
    OLLAMA_AVAILABLE = True
except ImportError:
    OLLAMA_AVAILABLE = False

from agents.local_rag_agent import LocalRAGAgent
from agents.arxiv_agent import ArxivAgent
from agents.youtube_agent import YouTubeAgent
from agents.github_agent import GitHubAgent
from agents.web_agent import WebAgent
from orchestrator.state import AgentState


def create_llm(provider=None):
    """Create LLM instance based on provider."""
    provider = provider or os.getenv("LLM_PROVIDER", "gemini")
    
    if provider == "gemini":
        if not GEMINI_AVAILABLE:
            pytest.skip("langchain_google_genai not installed")
        
        api_key = os.getenv("GOOGLE_API_KEY")
        if not api_key:
            pytest.skip("GOOGLE_API_KEY environment variable not set")
        
        model_name = os.getenv("GEMINI_MODEL", "gemini-pro")
        return ChatGoogleGenerativeAI(
            model=model_name,
            temperature=config.LLM_TEMPERATURE,
            google_api_key=api_key
        )
    
    elif provider == "ollama":
        if not OLLAMA_AVAILABLE:
            pytest.skip("langchain_ollama not installed")
        
        return ChatOllama(
            model=config.LLM_MODEL,
            temperature=config.LLM_TEMPERATURE
        )
    else:
        pytest.skip(f"Unknown provider: {provider}")


@pytest.fixture
def real_llm():
    """Create real LLM instance."""
    return create_llm()


@pytest.fixture
def real_config():
    """Create config with real API keys from environment."""
    cfg = Mock()
    
    # ArXiv - no key needed
    cfg.MAX_ARXIV_RESULTS = 5
    cfg.ENABLE_ARXIV_AGENT = True
    
    # GitHub - optional token
    cfg.GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", None)
    cfg.USE_GITHUB_MCP = False
    cfg.ENABLE_GITHUB_AGENT = True
    
    # YouTube - optional API key
    cfg.YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY", None)
    cfg.ENABLE_YOUTUBE_AGENT = True
    
    # Web - optional Tavily key
    cfg.TAVILY_API_KEY = os.getenv("TAVILY_API_KEY", None)
    cfg.USE_WEB_SEARCH_MCP = False
    cfg.MAX_WEB_RESULTS = 5
    cfg.ENABLE_WEB_AGENT = True
    
    return cfg


@pytest.fixture
def real_collection():
    """Create or get real vector store collection."""
    from db.vector_db_manager import VectorDbManager
    
    vector_db = VectorDbManager()
    vector_db.create_collection(config.CHILD_COLLECTION)
    collection = vector_db.get_collection(config.CHILD_COLLECTION)
    
    return collection


@pytest.fixture
def graph_config():
    """Create graph config with thread_id for checkpointer."""
    return {"configurable": {"thread_id": str(uuid.uuid4())}}


@pytest.mark.integration
class TestArxivAgentReal:
    """Test ArxivAgent with real LLM and APIs."""
    
    def test_arxiv_agent_search(self, real_llm, real_config, graph_config):
        """Test ArxivAgent searching for papers."""
        agent = ArxivAgent(real_llm, real_config)
        
        # Create subgraph
        subgraph = agent.create_agent_subgraph()
        
        # Create state with query
        state = AgentState(
            question="Find recent papers about transformer neural networks",
            question_index=0,
            messages=[]
        )
        
        # Execute agent subgraph
        result = subgraph.invoke(state, graph_config)
        
        # Verify results
        assert "final_answer" in result
        assert len(result["final_answer"]) > 0
        assert "agent_answers" in result
        assert len(result["agent_answers"]) > 0
        
        print(f"\n✓ ArxivAgent Answer:")
        print(f"  {result['final_answer'][:200]}...")
        citations = result['agent_answers'][0].get('citations', [])
        print(f"  Citations: {len(citations)}")
        if citations:
            print(f"  Example citation: {citations[0].get('title', 'Unknown')[:60]}...")
    
    def test_arxiv_agent_get_paper(self, real_llm, real_config, graph_config):
        """Test ArxivAgent getting specific paper."""
        agent = ArxivAgent(real_llm, real_config)
        subgraph = agent.create_agent_subgraph()
        
        state = AgentState(
            question="Get the paper with ID 1706.03762 and summarize it",
            question_index=0,
            messages=[]
        )
        
        result = subgraph.invoke(state, graph_config)
        
        assert "final_answer" in result
        print(f"\n✓ Paper Summary:")
        print(f"  {result['final_answer'][:300]}...")


@pytest.mark.integration
class TestYouTubeAgentReal:
    """Test YouTubeAgent with real LLM and APIs."""
    
    def test_youtube_agent_transcript(self, real_llm, real_config, graph_config):
        """Test YouTubeAgent extracting transcript."""
        agent = YouTubeAgent(real_llm, real_config)
        subgraph = agent.create_agent_subgraph()
        
        # Use a video with transcripts - try a few common ones
        test_videos = ["kqtD5dpn9C8", "dQw4w9WgXcQ", "jGwO_UgTS7I"]
        
        for video_id in test_videos:
            state = AgentState(
                question=f"Get transcript from video {video_id} and summarize it",
                question_index=0,
                messages=[]
            )
            
            result = subgraph.invoke(state, graph_config)
            
            # May fail if video has no transcripts
            if "Unable to generate" not in result.get("final_answer", ""):
                assert "final_answer" in result
                print(f"\n✓ YouTube Transcript Summary (video {video_id}):")
                print(f"  {result['final_answer'][:300]}...")
                return
        
        pytest.skip("No videos with available transcripts found")


@pytest.mark.integration
class TestGitHubAgentReal:
    """Test GitHubAgent with real LLM and APIs."""
    
    def test_github_agent_search(self, real_llm, real_config, graph_config):
        """Test GitHubAgent searching repositories."""
        agent = GitHubAgent(real_llm, real_config)
        subgraph = agent.create_agent_subgraph()
        
        state = AgentState(
            question="Find GitHub repositories about langchain",
            question_index=0,
            messages=[]
        )
        
        result = subgraph.invoke(state, graph_config)
        
        assert "final_answer" in result
        print(f"\n✓ GitHub Search Results:")
        print(f"  {result['final_answer'][:300]}...")
    
    def test_github_agent_readme(self, real_llm, real_config, graph_config):
        """Test GitHubAgent reading README."""
        agent = GitHubAgent(real_llm, real_config)
        subgraph = agent.create_agent_subgraph()
        
        state = AgentState(
            question="Get the README from langchain-ai/langchain and summarize it",
            question_index=0,
            messages=[]
        )
        
        result = subgraph.invoke(state, graph_config)
        
        assert "final_answer" in result
        print(f"\n✓ README Summary:")
        print(f"  {result['final_answer'][:300]}...")


@pytest.mark.integration
class TestWebAgentReal:
    """Test WebAgent with real LLM and APIs."""
    
    def test_web_agent_extract(self, real_llm, real_config, graph_config):
        """Test WebAgent extracting webpage content."""
        agent = WebAgent(real_llm, real_config)
        subgraph = agent.create_agent_subgraph()
        
        state = AgentState(
            question="Extract and summarize content from https://www.python.org",
            question_index=0,
            messages=[]
        )
        
        result = subgraph.invoke(state, graph_config)
        
        assert "final_answer" in result
        print(f"\n✓ Web Content Summary:")
        print(f"  {result['final_answer'][:300]}...")
    
    @pytest.mark.skipif(
        not os.getenv("TAVILY_API_KEY"),
        reason="TAVILY_API_KEY not set"
    )
    def test_web_agent_search(self, real_llm, real_config, graph_config):
        """Test WebAgent searching the web."""
        agent = WebAgent(real_llm, real_config)
        subgraph = agent.create_agent_subgraph()
        
        state = AgentState(
            question="Search the web for 'python programming tutorial'",
            question_index=0,
            messages=[]
        )
        
        result = subgraph.invoke(state, graph_config)
        
        assert "final_answer" in result
        print(f"\n✓ Web Search Results:")
        print(f"  {result['final_answer'][:300]}...")


@pytest.mark.integration
class TestLocalRAGAgentReal:
    """Test LocalRAGAgent with real LLM and collection."""
    
    def test_local_rag_agent_search(self, real_llm, real_config, real_collection, graph_config):
        """Test LocalRAGAgent searching documents."""
        agent = LocalRAGAgent(real_llm, real_collection, real_config)
        subgraph = agent.create_agent_subgraph()
        
        state = AgentState(
            question="What is machine learning?",
            question_index=0,
            messages=[]
        )
        
        result = subgraph.invoke(state, graph_config)
        
        assert "final_answer" in result
        print(f"\n✓ Local RAG Answer:")
        print(f"  {result['final_answer'][:300]}...")
        citations = result['agent_answers'][0].get('citations', [])
        print(f"  Citations: {len(citations)}")


@pytest.mark.integration
class TestAgentSubgraphCreation:
    """Test that all agents can create and execute subgraphs."""
    
    def test_all_agents_create_subgraphs(self, real_llm, real_config, real_collection):
        """Test that all agents can create subgraphs."""
        agents = [
            ("LocalRAGAgent", LocalRAGAgent(real_llm, real_collection, real_config)),
            ("ArxivAgent", ArxivAgent(real_llm, real_config)),
            ("YouTubeAgent", YouTubeAgent(real_llm, real_config)),
            ("GitHubAgent", GitHubAgent(real_llm, real_config)),
            ("WebAgent", WebAgent(real_llm, real_config)),
        ]
        
        for name, agent in agents:
            subgraph = agent.create_agent_subgraph()
            assert subgraph is not None
            print(f"✓ {name} subgraph created successfully")

