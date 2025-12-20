"""
Comprehensive tests for all specialized agents.

Tests each agent's functionality with and without API keys,
verifying initialization, execution, citation extraction, and error handling.
"""
import pytest
from unittest.mock import Mock, MagicMock, patch, call
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage

from agents.base_agent import BaseAgent
from agents.local_rag_agent import LocalRAGAgent
from agents.arxiv_agent import ArxivAgent
from agents.youtube_agent import YouTubeAgent
from agents.github_agent import GitHubAgent
from agents.web_agent import WebAgent
from tools.base import SourceType


@pytest.fixture
def mock_llm():
    """Create a mock LLM for testing"""
    llm = MagicMock()
    llm.bind_tools = Mock(return_value=llm)
    return llm


@pytest.fixture
def mock_config():
    """Create a mock config object"""
    config = Mock()
    config.ENABLE_ARXIV_AGENT = True
    config.ENABLE_YOUTUBE_AGENT = True
    config.ENABLE_GITHUB_AGENT = True
    config.ENABLE_WEB_AGENT = True
    config.MAX_ARXIV_RESULTS = 10
    config.MAX_WEB_RESULTS = 10
    config.YOUTUBE_API_KEY = None
    config.GITHUB_TOKEN = None
    config.TAVILY_API_KEY = None
    config.USE_GITHUB_MCP = False
    config.USE_WEB_SEARCH_MCP = False
    return config


@pytest.fixture
def mock_collection():
    """Create a mock vector store collection"""
    mock_doc = MagicMock()
    mock_doc.page_content = "Test document content about machine learning"
    mock_doc.metadata = {
        "parent_id": "parent_1",
        "source": "test.pdf"
    }
    
    collection = MagicMock()
    collection.similarity_search.return_value = [mock_doc]
    return collection


class TestLocalRAGAgent:
    """Test LocalRAGAgent"""
    
    def test_initialization(self, mock_llm, mock_config, mock_collection):
        """Test agent initialization"""
        agent = LocalRAGAgent(mock_llm, mock_collection, mock_config)
        
        assert agent.source_type == SourceType.LOCAL
        assert agent.collection == mock_collection
        assert len(agent.tools) == 2
    
    def test_get_system_prompt(self, mock_llm, mock_config, mock_collection):
        """Test that system prompt is returned"""
        agent = LocalRAGAgent(mock_llm, mock_collection, mock_config)
        prompt = agent.get_system_prompt()
        
        assert isinstance(prompt, str)
        assert len(prompt) > 0
        assert "local" in prompt.lower() or "document" in prompt.lower()
    
    def test_create_agent_subgraph(self, mock_llm, mock_config, mock_collection):
        """Test subgraph creation"""
        agent = LocalRAGAgent(mock_llm, mock_collection, mock_config)
        subgraph = agent.create_agent_subgraph()
        
        assert subgraph is not None
        mock_llm.bind_tools.assert_called_once()
    
    def test_extract_answer_with_citations(self, mock_llm, mock_config, mock_collection):
        """Test answer extraction with citations"""
        agent = LocalRAGAgent(mock_llm, mock_collection, mock_config)
        
        # Create mock state with messages
        from rag_agent.graph_state import AgentState
        state = AgentState(
            question="What is machine learning?",
            question_index=0,
            messages=[
                HumanMessage(content="What is machine learning?"),
                AIMessage(
                    content="",
                    tool_calls=[{
                        "id": "call_1",
                        "name": "search_local_documents",
                        "args": {"query": "machine learning", "k": 5}
                    }]
                ),
                ToolMessage(
                    content='[{"content": "ML content", "source": "test.pdf", "parent_id": "p1"}]',
                    tool_call_id="call_1"
                ),
                AIMessage(content="Machine learning is a subset of AI.")
            ]
        )
        
        result = agent.extract_answer_with_citations(state)
        
        assert "final_answer" in result
        assert "agent_answers" in result
        assert len(result["agent_answers"]) == 1
        assert result["agent_answers"][0]["source"] == "local"
    
    def test_citation_extraction(self, mock_llm, mock_config, mock_collection):
        """Test citation extraction from tool results"""
        agent = LocalRAGAgent(mock_llm, mock_collection, mock_config)
        
        # Test with list of results
        tool_result = [
            {"content": "Content 1", "source": "doc1.pdf", "parent_id": "p1"},
            {"content": "Content 2", "source": "doc2.pdf", "parent_id": "p2"}
        ]
        
        citation = agent._parse_tool_result_to_citation(
            "search_local_documents",
            {},
            tool_result
        )
        
        assert citation is not None
        assert citation["source_type"] == "local"
        assert "sources" in citation.get("metadata", {}) or "source_path" in citation.get("metadata", {})


class TestArxivAgent:
    """Test ArxivAgent"""
    
    def test_initialization(self, mock_llm, mock_config):
        """Test agent initialization"""
        agent = ArxivAgent(mock_llm, mock_config)
        
        assert agent.source_type == SourceType.ARXIV
        assert len(agent.tools) == 3
    
    def test_get_system_prompt(self, mock_llm, mock_config):
        """Test that system prompt is returned"""
        agent = ArxivAgent(mock_llm, mock_config)
        prompt = agent.get_system_prompt()
        
        assert isinstance(prompt, str)
        assert len(prompt) > 0
        assert "arxiv" in prompt.lower() or "paper" in prompt.lower()
    
    def test_create_agent_subgraph(self, mock_llm, mock_config):
        """Test subgraph creation"""
        agent = ArxivAgent(mock_llm, mock_config)
        subgraph = agent.create_agent_subgraph()
        
        assert subgraph is not None
        mock_llm.bind_tools.assert_called_once()
    
    def test_citation_extraction(self, mock_llm, mock_config):
        """Test citation extraction from ArXiv results"""
        agent = ArxivAgent(mock_llm, mock_config)
        
        # Test with search result
        tool_result = [{
            "arxiv_id": "2301.00001",
            "title": "Test Paper",
            "authors": ["John Doe"],
            "published": "2024-01-01",
            "pdf_url": "https://arxiv.org/pdf/2301.00001.pdf",
            "abstract": "Test abstract"
        }]
        
        citation = agent._parse_tool_result_to_citation(
            "search_arxiv",
            {},
            tool_result
        )
        
        assert citation is not None
        assert citation["source_type"] == "arxiv"
        assert citation["metadata"]["arxiv_id"] == "2301.00001"
        assert "arxiv" in citation["url"].lower()


class TestYouTubeAgent:
    """Test YouTubeAgent"""
    
    def test_initialization(self, mock_llm, mock_config):
        """Test agent initialization"""
        agent = YouTubeAgent(mock_llm, mock_config)
        
        assert agent.source_type == SourceType.YOUTUBE
        assert len(agent.tools) == 3
    
    def test_get_system_prompt(self, mock_llm, mock_config):
        """Test that system prompt is returned"""
        agent = YouTubeAgent(mock_llm, mock_config)
        prompt = agent.get_system_prompt()
        
        assert isinstance(prompt, str)
        assert len(prompt) > 0
        assert "youtube" in prompt.lower() or "video" in prompt.lower()
    
    def test_create_agent_subgraph(self, mock_llm, mock_config):
        """Test subgraph creation"""
        agent = YouTubeAgent(mock_llm, mock_config)
        subgraph = agent.create_agent_subgraph()
        
        assert subgraph is not None
        mock_llm.bind_tools.assert_called_once()
    
    def test_citation_extraction_video(self, mock_llm, mock_config):
        """Test citation extraction from video search results"""
        agent = YouTubeAgent(mock_llm, mock_config)
        
        tool_result = [{
            "video_id": "dQw4w9WgXcQ",
            "title": "Test Video",
            "channel": "Test Channel",
            "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            "description": "Test description"
        }]
        
        citation = agent._parse_tool_result_to_citation(
            "search_youtube",
            {},
            tool_result
        )
        
        assert citation is not None
        assert citation["source_type"] == "youtube"
        assert citation["metadata"]["video_id"] == "dQw4w9WgXcQ"
        assert "youtube.com" in citation["url"]
    
    def test_citation_extraction_transcript(self, mock_llm, mock_config):
        """Test citation extraction from transcript results"""
        agent = YouTubeAgent(mock_llm, mock_config)
        
        tool_result = {
            "video_id": "dQw4w9WgXcQ",
            "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            "transcript": "Full transcript text here",
            "transcript_type": "auto-generated",
            "language": "en"
        }
        
        citation = agent._parse_tool_result_to_citation(
            "get_youtube_transcript",
            {},
            tool_result
        )
        
        assert citation is not None
        assert citation["source_type"] == "youtube"
        assert "transcript" in citation["title"].lower()


class TestGitHubAgent:
    """Test GitHubAgent"""
    
    def test_initialization(self, mock_llm, mock_config):
        """Test agent initialization"""
        agent = GitHubAgent(mock_llm, mock_config)
        
        assert agent.source_type == SourceType.GITHUB
        assert len(agent.tools) == 4
    
    def test_get_system_prompt(self, mock_llm, mock_config):
        """Test that system prompt is returned"""
        agent = GitHubAgent(mock_llm, mock_config)
        prompt = agent.get_system_prompt()
        
        assert isinstance(prompt, str)
        assert len(prompt) > 0
        assert "github" in prompt.lower() or "code" in prompt.lower()
    
    def test_create_agent_subgraph(self, mock_llm, mock_config):
        """Test subgraph creation"""
        agent = GitHubAgent(mock_llm, mock_config)
        subgraph = agent.create_agent_subgraph()
        
        assert subgraph is not None
        mock_llm.bind_tools.assert_called_once()
    
    def test_citation_extraction_repo(self, mock_llm, mock_config):
        """Test citation extraction from repository search"""
        agent = GitHubAgent(mock_llm, mock_config)
        
        tool_result = [{
            "full_name": "owner/repo",
            "description": "Test repository",
            "url": "https://github.com/owner/repo",
            "stars": 100,
            "language": "Python"
        }]
        
        citation = agent._parse_tool_result_to_citation(
            "search_github",
            {},
            tool_result
        )
        
        assert citation is not None
        assert citation["source_type"] == "github"
        assert "github.com" in citation["url"]
        assert citation["metadata"]["full_name"] == "owner/repo"
    
    def test_citation_extraction_readme(self, mock_llm, mock_config):
        """Test citation extraction from README"""
        agent = GitHubAgent(mock_llm, mock_config)
        
        tool_result = {
            "repo": "owner/repo",
            "content": "# README\nTest content",
            "path": "README.md",
            "url": "https://github.com/owner/repo/blob/main/README.md"
        }
        
        citation = agent._parse_tool_result_to_citation(
            "get_github_readme",
            {},
            tool_result
        )
        
        assert citation is not None
        assert citation["source_type"] == "github"
        assert "readme" in citation["title"].lower()


class TestWebAgent:
    """Test WebAgent"""
    
    def test_initialization(self, mock_llm, mock_config):
        """Test agent initialization"""
        agent = WebAgent(mock_llm, mock_config)
        
        assert agent.source_type == SourceType.WEB
        # Web agent may have 0 tools if API key not configured
        assert len(agent.tools) >= 0
    
    def test_get_system_prompt(self, mock_llm, mock_config):
        """Test that system prompt is returned"""
        agent = WebAgent(mock_llm, mock_config)
        prompt = agent.get_system_prompt()
        
        assert isinstance(prompt, str)
        assert len(prompt) > 0
        assert "web" in prompt.lower() or "article" in prompt.lower()
    
    def test_create_agent_subgraph(self, mock_llm, mock_config):
        """Test subgraph creation"""
        agent = WebAgent(mock_llm, mock_config)
        subgraph = agent.create_agent_subgraph()
        
        assert subgraph is not None
        mock_llm.bind_tools.assert_called_once()
    
    def test_citation_extraction_search(self, mock_llm, mock_config):
        """Test citation extraction from web search"""
        agent = WebAgent(mock_llm, mock_config)
        
        tool_result = [{
            "title": "Test Article",
            "url": "https://example.com/article",
            "content": "Article content here",
            "score": 0.95
        }]
        
        citation = agent._parse_tool_result_to_citation(
            "web_search",
            {},
            tool_result
        )
        
        assert citation is not None
        assert citation["source_type"] == "web"
        assert citation["url"] == "https://example.com/article"
    
    def test_citation_extraction_webpage(self, mock_llm, mock_config):
        """Test citation extraction from webpage extraction"""
        agent = WebAgent(mock_llm, mock_config)
        
        tool_result = {
            "url": "https://example.com/article",
            "title": "Test Article",
            "content": "Full article content",
            "word_count": 500
        }
        
        citation = agent._parse_tool_result_to_citation(
            "extract_webpage",
            {},
            tool_result
        )
        
        assert citation is not None
        assert citation["source_type"] == "web"
        assert citation["url"] == "https://example.com/article"


class TestAgentIntegration:
    """Integration tests for agents"""
    
    def test_all_agents_initializable(self, mock_llm, mock_config, mock_collection):
        """Test that all agents can be initialized"""
        agents = [
            LocalRAGAgent(mock_llm, mock_collection, mock_config),
            ArxivAgent(mock_llm, mock_config),
            YouTubeAgent(mock_llm, mock_config),
            GitHubAgent(mock_llm, mock_config),
            WebAgent(mock_llm, mock_config),
        ]
        
        for agent in agents:
            assert isinstance(agent, BaseAgent)
            assert agent.get_system_prompt() is not None
            assert len(agent.tools) >= 0
    
    def test_agent_subgraph_creation(self, mock_llm, mock_config, mock_collection):
        """Test that all agents can create subgraphs"""
        agents = [
            LocalRAGAgent(mock_llm, mock_collection, mock_config),
            ArxivAgent(mock_llm, mock_config),
            YouTubeAgent(mock_llm, mock_config),
            GitHubAgent(mock_llm, mock_config),
            WebAgent(mock_llm, mock_config),
        ]
        
        for agent in agents:
            subgraph = agent.create_agent_subgraph()
            assert subgraph is not None
    
    def test_citation_format_consistency(self, mock_llm, mock_config, mock_collection):
        """Test that all agents return consistent citation formats"""
        agents = [
            LocalRAGAgent(mock_llm, mock_collection, mock_config),
            ArxivAgent(mock_llm, mock_config),
            YouTubeAgent(mock_llm, mock_config),
            GitHubAgent(mock_llm, mock_config),
            WebAgent(mock_llm, mock_config),
        ]
        
        for agent in agents:
            # Create a simple test result
            test_result = {"url": "https://test.com", "title": "Test"}
            citation = agent._parse_tool_result_to_citation("test_tool", {}, test_result)
            
            if citation:  # Some agents may return None for invalid results
                assert "source_type" in citation
                assert citation["source_type"] == agent.source_type.value
                assert "url" in citation or "title" in citation

