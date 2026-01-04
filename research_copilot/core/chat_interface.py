from langchain_core.messages import HumanMessage
from typing import Dict, List, Any, Tuple


def _extract_text_from_content(content) -> str:
    """
    Extract plain text from LLM response content.
    
    Handles:
    - Strings (returned as-is)
    - Lists of content blocks from Gemini: [{'type': 'text', 'text': '...', 'extras': {...}}]
    - Single dict content blocks
    - Other types (converted via str())
    
    Args:
        content: Content that may be string, list, or dict
        
    Returns:
        Plain string content
    """
    if isinstance(content, str):
        return content
    elif isinstance(content, list):
        # Handle list of content blocks (e.g., Google Gemini)
        text_parts = []
        for item in content:
            if isinstance(item, dict):
                # Extract 'text' field from content block dict
                if 'text' in item:
                    text_parts.append(item['text'])
                elif 'content' in item:
                    text_parts.append(item['content'])
                else:
                    # Skip malformed dicts
                    pass
            elif isinstance(item, str):
                text_parts.append(item)
            elif item is not None:
                text_parts.append(str(item))
        return " ".join(text_parts)
    elif isinstance(content, dict):
        # Handle single content block dict
        if 'text' in content:
            return content['text']
        elif 'content' in content:
            return content['content']
        else:
            return str(content)
    else:
        return str(content) if content else ""


class ChatInterface:
    
    def __init__(self, rag_system):
        self.rag_system = rag_system
        
    def chat(self, message, history):
        """
        Process chat message and return answer with research artifacts.
        
        Returns:
            Tuple of (answer_text, research_data) where research_data contains:
            - citations: List of citation objects
            - agent_results: Dict of results by agent type
            - sources: List of source types used
        """
        if not self.rag_system.agent_graph:
            return "⚠️ System not initialized!", {}
            
        try:
            result = self.rag_system.agent_graph.invoke(
                {"messages": [HumanMessage(content=message.strip())]},
                self.rag_system.get_config()
            )
            
            # Extract answer (handle Gemini's structured content format)
            raw_content = result["messages"][-1].content if result.get("messages") else "No response generated."
            answer_text = _extract_text_from_content(raw_content)
            
            # Extract research artifacts
            citations = result.get("citations", [])
            agent_results = result.get("agent_results", {})
            
            # Build research data structure
            research_data = {
                "citations": citations,
                "agent_results": agent_results,
                "sources": list(agent_results.keys()) if agent_results else [],
                "citation_count": len(citations)
            }
            
            return answer_text, research_data
            
        except Exception as e:
            return f"❌ Error: {str(e)}", {}
    
    def clear_session(self):
        self.rag_system.reset_thread()