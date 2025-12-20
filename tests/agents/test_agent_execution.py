"""
Tests for agent execution with mocked LLM responses.

These tests verify that agents can execute queries and handle
tool calling loops correctly.
"""
import pytest
from unittest.mock import Mock, MagicMock, patch
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage

from agents.local_rag_agent import LocalRAGAgent
from agents.arxiv_agent import ArxivAgent
from agents.youtube_agent import YouTubeAgent
from agents.github_agent import GitHubAgent
from agents.web_agent import WebAgent
from rag_agent.graph_state import AgentState


@pytest.fixture
def mock_llm_with_tools():
    """Create a mock LLM that simulates tool calling"""
    llm = MagicMock()
    
    # First call: agent calls tool
    tool_call_response = AIMessage(
        content="",
        tool_calls=[{
            "id": "call_1",
            "name": "test_tool",
            "args": {"query": "test"}
        }]
    )
    
    # Second call: agent provides answer
    final_response = AIMessage(content="This is the final answer.")
    
    # Simulate tool calling loop
    call_count = 0
    def invoke_side_effect(messages):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return tool_call_response
        else:
            return final_response
    
    llm.invoke = Mock(side_effect=invoke_side_effect)
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
    mock_doc.page_content = "Test document content"
    mock_doc.metadata = {
        "parent_id": "parent_1",
        "source": "test.pdf"
    }
    
    collection = MagicMock()
    collection.similarity_search.return_value = [mock_doc]
    return collection


class TestAgentExecution:
    """Test agent execution flow"""
    
    def test_local_rag_agent_execution(self, mock_llm_with_tools, mock_config, mock_collection):
        """Test LocalRAGAgent execution"""
        agent = LocalRAGAgent(mock_llm_with_tools, mock_collection, mock_config)
        
        # Create state with question
        state = AgentState(
            question="What is machine learning?",
            question_index=0,
            messages=[]
        )
        
        # Test that subgraph can be created
        subgraph = agent.create_agent_subgraph()
        assert subgraph is not None
        
        # Verify LLM was bound with tools
        mock_llm_with_tools.bind_tools.assert_called_once()
    
    def test_arxiv_agent_execution(self, mock_llm_with_tools, mock_config):
        """Test ArxivAgent execution"""
        agent = ArxivAgent(mock_llm_with_tools, mock_config)
        
        # Test subgraph creation
        subgraph = agent.create_agent_subgraph()
        assert subgraph is not None
        
        # Verify tools are bound
        mock_llm_with_tools.bind_tools.assert_called_once()
        assert len(agent.tools) == 3
    
    def test_youtube_agent_execution(self, mock_llm_with_tools, mock_config):
        """Test YouTubeAgent execution"""
        agent = YouTubeAgent(mock_llm_with_tools, mock_config)
        
        # Test subgraph creation
        subgraph = agent.create_agent_subgraph()
        assert subgraph is not None
        
        # Verify tools are bound
        mock_llm_with_tools.bind_tools.assert_called_once()
        assert len(agent.tools) == 3
    
    def test_github_agent_execution(self, mock_llm_with_tools, mock_config):
        """Test GitHubAgent execution"""
        agent = GitHubAgent(mock_llm_with_tools, mock_config)
        
        # Test subgraph creation
        subgraph = agent.create_agent_subgraph()
        assert subgraph is not None
        
        # Verify tools are bound
        mock_llm_with_tools.bind_tools.assert_called_once()
        assert len(agent.tools) == 4
    
    def test_web_agent_execution(self, mock_llm_with_tools, mock_config):
        """Test WebAgent execution"""
        agent = WebAgent(mock_llm_with_tools, mock_config)
        
        # Test subgraph creation
        subgraph = agent.create_agent_subgraph()
        assert subgraph is not None
        
        # Verify tools are bound (may be 0 if no API key)
        mock_llm_with_tools.bind_tools.assert_called_once()
        assert len(agent.tools) >= 0
    
    def test_answer_extraction_with_tool_calls(self, mock_llm_with_tools, mock_config, mock_collection):
        """Test answer extraction when tools were called"""
        agent = LocalRAGAgent(mock_llm_with_tools, mock_collection, mock_config)
        
        # Create state with tool calls and results
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
                    content='[{"content": "ML is AI", "source": "test.pdf", "parent_id": "p1"}]',
                    tool_call_id="call_1"
                ),
                AIMessage(content="Machine learning is a subset of artificial intelligence.")
            ]
        )
        
        result = agent.extract_answer_with_citations(state)
        
        assert "final_answer" in result
        assert result["final_answer"] == "Machine learning is a subset of artificial intelligence."
        assert "agent_answers" in result
        assert len(result["agent_answers"]) == 1
        assert result["agent_answers"][0]["source"] == "local"
    
    def test_answer_extraction_no_tool_calls(self, mock_llm_with_tools, mock_config, mock_collection):
        """Test answer extraction when no tools were called"""
        agent = LocalRAGAgent(mock_llm_with_tools, mock_collection, mock_config)
        
        # Create state without tool calls
        state = AgentState(
            question="Hello",
            question_index=0,
            messages=[
                HumanMessage(content="Hello"),
                AIMessage(content="Hello! How can I help you?")
            ]
        )
        
        result = agent.extract_answer_with_citations(state)
        
        assert "final_answer" in result
        assert result["final_answer"] == "Hello! How can I help you?"
        assert len(result["agent_answers"]) == 1
    
    def test_answer_extraction_no_answer(self, mock_llm_with_tools, mock_config, mock_collection):
        """Test answer extraction when no answer is found"""
        agent = LocalRAGAgent(mock_llm_with_tools, mock_collection, mock_config)
        
        # Create state with only tool calls, no final answer
        state = AgentState(
            question="Test",
            question_index=0,
            messages=[
                HumanMessage(content="Test"),
                AIMessage(
                    content="",
                    tool_calls=[{"id": "call_1", "name": "test_tool", "args": {}}]
                )
            ]
        )
        
        result = agent.extract_answer_with_citations(state)
        
        assert "final_answer" in result
        assert "Unable to generate" in result["final_answer"]
        assert len(result["agent_answers"]) == 1

