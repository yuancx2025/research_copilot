from langchain_core.messages import HumanMessage
from typing import Dict, List, Any, Tuple

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
            
            # Extract answer
            answer_text = result["messages"][-1].content if result.get("messages") else "No response generated."
            
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