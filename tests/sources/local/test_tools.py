"""
Tests for tools/local_tools.py - Local document search tools
"""
import pytest
from langchain_core.tools import ToolException
from unittest.mock import Mock, MagicMock, patch
from research_copilot.sources.local.tools import LocalToolkit
from research_copilot.runtime.base_toolkit import SourceType


class TestLocalToolkit:
    """Test LocalToolkit class"""
    
    def test_source_type(self):
        """Test that LocalToolkit has correct source type"""
        config = Mock()
        toolkit = LocalToolkit(config)
        
        assert toolkit.source_type == SourceType.LOCAL
    
    def test_is_always_available(self):
        """Test that local tools are always available"""
        config = Mock()
        toolkit = LocalToolkit(config)
        
        assert toolkit.is_available() is True
    
    def test_search_without_collection(self):
        """Test search when collection is not set"""
        config = Mock()
        toolkit = LocalToolkit(config)
        
        with pytest.raises(ToolException, match="No document collection"):
            toolkit._search_child_chunks("test query")
    
    def test_search_with_collection(self):
        """Test search with a mock collection"""
        config = Mock()
        toolkit = LocalToolkit(config)
        
        # Mock collection and search results
        mock_doc = MagicMock()
        mock_doc.page_content = "Test content"
        mock_doc.metadata = {
            "parent_id": "parent_1",
            "source": "test.pdf"
        }
        
        mock_collection = MagicMock()
        mock_collection.similarity_search.return_value = [mock_doc]
        
        toolkit.set_collection(mock_collection)
        
        results = toolkit._search_child_chunks("test query", k=5)
        
        assert len(results) == 1
        assert results[0]["content"] == "Test content"
        assert results[0]["source_type"] == "local"
        mock_collection.similarity_search.assert_called_once()
    
    def test_retrieve_parent_chunks(self):
        """Test retrieving parent chunks"""
        config = Mock()
        toolkit = LocalToolkit(config)
        
        # Mock parent store manager
        mock_chunks = [
            {
                "content": "Full parent content",
                "parent_id": "parent_1",
                "metadata": {"source": "test.pdf"}
            }
        ]
        
        toolkit.parent_store_manager.load_many = Mock(return_value=mock_chunks)
        
        results = toolkit._retrieve_parent_chunks(["parent_1"])
        
        assert len(results) == 1
        assert results[0]["content"] == "Full parent content"
        assert results[0]["source_type"] == "local"
    
    def test_create_tools(self):
        """Test that tools are created correctly"""
        config = Mock()
        toolkit = LocalToolkit(config)
        
        tools = toolkit.create_tools()
        
        assert len(tools) == 2
        assert tools[0].name == "search_local_documents"
        assert tools[1].name == "retrieve_document_context"
    
    def test_search_error_handling(self):
        """Test error handling in search"""
        config = Mock()
        toolkit = LocalToolkit(config)
        
        mock_collection = MagicMock()
        mock_collection.similarity_search.side_effect = Exception("Search failed")
        
        toolkit.set_collection(mock_collection)
        
        with pytest.raises(ToolException, match="Search failed"):
            toolkit._search_child_chunks("test")
    
    def test_retrieve_error_handling(self):
        """Test error handling in retrieval"""
        config = Mock()
        toolkit = LocalToolkit(config)
        
        toolkit.parent_store_manager.load_many = Mock(side_effect=Exception("Load failed"))
        
        with pytest.raises(ToolException, match="Retrieval failed"):
            toolkit._retrieve_parent_chunks(["parent_1"])



def test_tool_failure_reaches_agent_as_error_message_and_is_traced():
    """M7: the agent's ToolNode must see an error result, not a list it reads as 'no documents'."""
    from langchain_core.messages import AIMessage
    from langgraph.prebuilt import ToolNode
    from research_copilot.evals.tracing import RunTracer

    toolkit = LocalToolkit(Mock())
    broken = MagicMock()
    broken.similarity_search.side_effect = RuntimeError("qdrant unavailable")
    toolkit.set_collection(broken)
    search = toolkit.create_tools()[0]
    from langgraph.graph import END, START, MessagesState, StateGraph
    builder = StateGraph(MessagesState)
    builder.add_node("tools", ToolNode([search], handle_tool_errors=lambda exc: "Tool failed. Check connection or permissions."))
    builder.add_edge(START, "tools")
    builder.add_edge("tools", END)
    tracer = RunTracer()
    call = {"id": "c1", "name": search.name, "args": {"query": "q"}}
    out = builder.compile().invoke({"messages": [AIMessage(content="", tool_calls=[call])]},
                                   config={"callbacks": [tracer]})
    out = {"messages": out["messages"][1:]}
    [message] = out["messages"]
    assert message.status == "error"
    assert tracer.summary()["tools"]["errors"] == 1
