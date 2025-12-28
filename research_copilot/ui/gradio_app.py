import gradio as gr
from research_copilot.core.chat_interface import ChatInterface
from research_copilot.core.document_manager import DocumentManager
from research_copilot.core.rag_system import RAGSystem
from research_copilot.ui.research_formatter import format_citations_markdown, format_agent_results_summary
from research_copilot.ui.css import custom_css
from research_copilot.config import settings as config
import logging

logger = logging.getLogger(__name__)


def is_notion_configured():
    """Check if Notion is configured (either via MCP or Direct API)."""
    # MCP mode: USE_NOTION_MCP=True and NOTION_MCP_COMMAND set
    mcp_configured = (
        getattr(config, 'USE_NOTION_MCP', False) and 
        getattr(config, 'NOTION_MCP_COMMAND', None)
    )
    # Direct API mode: NOTION_API_KEY and NOTION_PARENT_PAGE_ID set
    direct_api_configured = (
        getattr(config, 'NOTION_API_KEY', None) and 
        getattr(config, 'NOTION_PARENT_PAGE_ID', None)
    )
    return mcp_configured or direct_api_configured


def create_gradio_ui():
    rag_system = RAGSystem()
    rag_system.initialize()
    
    doc_manager = DocumentManager(rag_system)
    chat_interface = ChatInterface(rag_system)
    
    # Store last research data for study plan creation
    last_research_data = {}
    last_query = ""
    
    def format_file_list():
        files = doc_manager.get_markdown_files()
        if not files:
            return "📭 No documents available in the knowledge base"
        return "\n".join([f"{f}" for f in files])
    
    def upload_handler(files, progress=gr.Progress()):
        if not files:
            return None, format_file_list()
            
        added, skipped = doc_manager.add_documents(
            files, 
            progress_callback=lambda p, desc: progress(p, desc=desc)
        )
        
        gr.Info(f"✅ Added: {added} | Skipped: {skipped}")
        return None, format_file_list()
    
    def clear_handler():
        doc_manager.clear_all()
        gr.Info(f"🗑️ Removed all documents")
        return format_file_list()
    
    def chat_handler(msg, hist):
        """Handler for Chat tab - returns only the answer string."""
        answer, research_data = chat_interface.chat(msg, hist)
        # gr.ChatInterface manages history automatically, so just return the answer
        return answer
    
    def research_chat_handler(msg, hist):
        """Handler for Research tab that returns both answer and artifacts."""
        nonlocal last_research_data, last_query
        
        answer, research_data = chat_interface.chat(msg, hist)
        
        # Store research data for study plan creation
        last_research_data = research_data.copy()
        last_research_data["answer_text"] = answer
        last_query = msg.strip()
        
        # Initialize history if None
        if hist is None:
            hist = []
        
        # Ensure msg is not empty
        if not msg or not msg.strip():
            if is_notion_configured():
                return [], "No citations yet.", "No sources used yet.", gr.update(interactive=False)
            return [], "No citations yet.", "No sources used yet."
        
        # Convert history to dictionary format if needed
        # Gradio 4.x expects: [{"role": "user", "content": "..."}, {"role": "assistant", "content": "..."}]
        formatted_hist = []
        
        # Convert existing history to dict format if it's in tuple format
        for item in hist:
            if isinstance(item, tuple) and len(item) == 2:
                # Convert tuple (user_msg, bot_msg) to dict format
                formatted_hist.append({"role": "user", "content": item[0]})
                formatted_hist.append({"role": "assistant", "content": item[1]})
            elif isinstance(item, dict):
                # Already in dict format
                formatted_hist.append(item)
        
        # Add new messages
        formatted_hist.append({"role": "user", "content": msg})
        formatted_hist.append({"role": "assistant", "content": answer})
        
        # Format citations for display
        citations = research_data.get("citations", [])
        citations_markdown = format_citations_markdown(citations) if citations else "No citations found."
        
        # Format agent results summary
        agent_results = research_data.get("agent_results", {})
        sources_summary = format_agent_results_summary(agent_results)
        
        # Enable Notion button if we have citations and Notion is configured
        notion_button_enabled = (
            is_notion_configured() and 
            len(citations) > 0
        )
        
        return formatted_hist, citations_markdown, sources_summary, gr.update(interactive=notion_button_enabled)
    
    def clear_chat_handler():
        chat_interface.clear_session()
    
    def clear_research_handler():
        nonlocal last_research_data, last_query
        chat_interface.clear_session()
        last_research_data = {}
        last_query = ""
        return [], "*No citations yet.*", "*No sources used yet.*", gr.update(interactive=False)
    
    def create_notion_study_plan():
        """Create a Notion study plan using the orchestrator and Notion agent."""
        nonlocal last_research_data, last_query
        
        
        if not is_notion_configured():
            return "❌ Notion is not configured. Set either:\n- MCP mode: USE_NOTION_MCP=true and NOTION_MCP_COMMAND\n- Direct API mode: NOTION_API_KEY and NOTION_PARENT_PAGE_ID"
        
        if not last_research_data or not last_query:
            return "❌ No research data available. Please perform a research query first."
        
        citations = last_research_data.get("citations", [])
        if not citations:
            return "❌ No citations found. Please perform a research query with results first."
        
        parent_page_id = getattr(config, 'NOTION_PARENT_PAGE_ID', None)
        if not parent_page_id:
            return "❌ NOTION_PARENT_PAGE_ID not configured. Please set it in your environment variables."
        
        try:
            # Format research data for Notion agent
            answer_text = last_research_data.get("answer_text", "")
            agent_results = last_research_data.get("agent_results", {})
            
            # Create a formatted message for the Notion agent
            # The agent will parse this to extract research data
            import json
            research_context = {
                "query": last_query,
                "citations": citations,
                "answer": answer_text,
                "agent_results": agent_results,
                "parent_page_id": parent_page_id
            }
            
            # Format as a structured message for the agent
            notion_query = f"""Create a study plan in Notion with the following research data:

Research Query: {last_query}

Research Summary:
{answer_text[:1000]}

Citations ({len(citations)} total):
{json.dumps(citations[:10], indent=2)[:2000]}

Parent Page ID: {parent_page_id}

Please create a comprehensive study plan with:
- Overview section
- Learning objectives
- Key concepts
- Resources organized by type
- Timeline
- Next steps

Use the notion-create-pages tool to create the page."""
            
            # Invoke orchestrator with create_study_plan flag
            from langchain_core.messages import HumanMessage
            
            
            result = rag_system.agent_graph.invoke(
                {
                    "messages": [HumanMessage(content=notion_query)],
                    "create_study_plan": True,
                    "originalQuery": last_query,
                    "citations": citations,
                    "agent_results": agent_results
                },
                rag_system.get_config()
            )
            
            
            # Extract Notion page URL from result
            final_message = result.get("messages", [])[-1] if result.get("messages") else None
            if final_message:
                answer_content = final_message.content if hasattr(final_message, 'content') else str(final_message)
                
                # Look for URL in the answer
                import re
                url_pattern = r'https?://[^\s\)]+'
                urls = re.findall(url_pattern, answer_content)
                
                if urls:
                    page_url = urls[0]
                    return f"✅ Study plan created successfully! [View in Notion]({page_url})"
                else:
                    # Check state for notion_page_url
                    notion_url = result.get("notion_page_url", "")
                    if notion_url:
                        return f"✅ Study plan created successfully! [View in Notion]({notion_url})"
                    else:
                        return f"✅ Study plan creation initiated. Response: {answer_content[:200]}..."
            
            return "✅ Study plan creation completed. Check Notion for the new page."
        
        except Exception as e:
            logger.error(f"Failed to create Notion study plan: {e}")
            import traceback
            traceback.print_exc()
            return f"❌ Error creating study plan: {str(e)}"
    
    # Create theme (will be passed to launch() in Gradio 6.0)
    theme = gr.themes.Base(
        primary_hue="blue",
        secondary_hue="gray",
        neutral_hue="gray",
        font=("SF Pro Display", "system-ui", "sans-serif"),
    ).set(
        body_background_fill="#0a0a0a",
        body_background_fill_dark="#0a0a0a",
        block_background_fill="#141414",
        block_background_fill_dark="#141414",
        block_border_color="#333333",
        block_border_color_dark="#333333",
        input_background_fill="#1e1e1e",
        input_background_fill_dark="#1e1e1e",
        button_primary_background_fill="#3b82f6",
        button_primary_background_fill_dark="#3b82f6",
        button_primary_text_color="white",
        button_primary_text_color_dark="white",
    )
    
    with gr.Blocks(title="Research Copilot") as demo:
        
        with gr.Tab("Documents", elem_id="doc-management-tab"):
            gr.Markdown("## 📄 Add New Documents")
            gr.Markdown("Upload PDF or Markdown files. Duplicates will be automatically skipped.")
            
            files_input = gr.File(
                label="Drop PDF or Markdown files here",
                file_count="multiple",
                type="filepath",
                height=200,
                show_label=False
            )
            
            add_btn = gr.Button("Add Documents", variant="primary", size="md")
            
            gr.Markdown("## Current Documents in the Knowledge Base")
            file_list = gr.Textbox(
                value=format_file_list(),
                interactive=False,
                lines = 7,
                max_lines=10,
                elem_id="file-list-box",
                show_label=False
            )
            
            with gr.Row():
                refresh_btn = gr.Button("Refresh", size="md")
                clear_btn = gr.Button("Clear All", variant="stop", size="md")
            
            add_btn.click(
                upload_handler, 
                [files_input], 
                [files_input, file_list], 
                show_progress="corner"
            )
            refresh_btn.click(format_file_list, None, file_list)
            clear_btn.click(clear_handler, None, file_list)
        
        with gr.Tab("💬 Chat"):
            chatbot = gr.Chatbot(
                height=600, 
                placeholder="💭 Ask me anything about your documents...",
                show_label=False,
                layout="bubble",
            )
            chatbot.clear(clear_chat_handler)
            
            gr.ChatInterface(fn=chat_handler, chatbot=chatbot)
        
        with gr.Tab("🔬 Research"):
            gr.Markdown("## 🔬 Research Assistant")
            gr.Markdown("Ask research questions and explore papers, videos, GitHub repos, and web articles.")
            
            # File upload section for Research tab
            with gr.Row():
                with gr.Column():
                    gr.Markdown("### 📄 Upload Documents for Research")
                    gr.Markdown("Upload PDF or Markdown files to index them. These documents will be searchable during research queries.")
                    
                    research_files_input = gr.File(
                        label="Drop PDF or Markdown files here",
                        file_count="multiple",
                        type="filepath",
                        height=120,
                        show_label=False
                    )
                    
                    research_upload_btn = gr.Button("📥 Index Documents", variant="primary", size="sm")
                    research_upload_status = gr.Markdown(value="", visible=False)
            
            with gr.Row():
                with gr.Column(scale=2):
                    research_chatbot = gr.Chatbot(
                        height=500,
                        placeholder="🔍 Ask a research question (e.g., 'What are the latest transformer architectures?')",
                        show_label=False,
                        elem_id="research-chatbot",
                        layout="bubble",
                    )
                    
                    research_input = gr.Textbox(
                        placeholder="Type your research question here...",
                        show_label=False,
                        container=False,
                        lines=1,
                        max_lines=3,
                    )
                    
                    with gr.Row():
                        research_submit_btn = gr.Button("🚀 Submit", variant="primary", scale=1)
                        research_clear_btn = gr.Button("🗑️ Clear", scale=1)
                
                with gr.Column(scale=1):
                    gr.Markdown("### 📊 Research Artifacts")
                    
                    sources_summary = gr.Markdown(
                        value="*No sources used yet.*",
                        elem_id="sources-summary"
                    )
                    
                    gr.Markdown("### Citations")
                    
                    citations_display = gr.Markdown(
                        value="No citations yet.",
                        elem_id="citations-display",
                        elem_classes="citations-box"
                    )
                    
                    # Notion Study Plan Button
                    if is_notion_configured():
                        gr.Markdown("---")
                        gr.Markdown("### 📝 Notion Integration")
                        
                        notion_button = gr.Button(
                            "📝 Create Study Plan in Notion",
                            variant="primary",
                            size="md",
                            interactive=False,
                            elem_id="notion-study-plan-btn"
                        )
                        
                        notion_status = gr.Markdown(
                            value="",
                            elem_id="notion-status"
                        )
            
            # File upload handler for Research tab
            def research_upload_handler(files, progress=gr.Progress()):
                if not files:
                    return "No files selected."
                
                added, skipped = doc_manager.add_documents(
                    files,
                    progress_callback=lambda p, desc: progress(p, desc=desc)
                )
                
                status_msg = f"✅ Indexed {added} document(s)"
                if skipped > 0:
                    status_msg += f" | Skipped {skipped} duplicate(s)"
                
                gr.Info(status_msg)
                return status_msg
            
            research_upload_btn.click(
                research_upload_handler,
                inputs=[research_files_input],
                outputs=[research_upload_status],
                show_progress="corner"
            )
            
            # Wire up events
            def submit_research(msg, hist):
                return research_chat_handler(msg, hist)
            
            # Determine outputs based on whether Notion is configured
            if is_notion_configured():
                research_outputs = [research_chatbot, citations_display, sources_summary, notion_button]
                clear_outputs = [research_chatbot, citations_display, sources_summary, notion_button]
            else:
                research_outputs = [research_chatbot, citations_display, sources_summary]
                clear_outputs = [research_chatbot, citations_display, sources_summary]
            
            research_submit_btn.click(
                submit_research,
                inputs=[research_input, research_chatbot],
                outputs=research_outputs
            ).then(
                lambda: "",  # Clear input
                outputs=[research_input]
            )
            
            research_input.submit(
                submit_research,
                inputs=[research_input, research_chatbot],
                outputs=research_outputs
            ).then(
                lambda: "",  # Clear input
                outputs=[research_input]
            )
            
            research_clear_btn.click(
                clear_research_handler,
                outputs=clear_outputs
            )
            
            # Notion study plan button handler
            if is_notion_configured():
                notion_button.click(
                    create_notion_study_plan,
                    outputs=[notion_status]
                )
    
    # Attach theme and css to demo for Gradio 6.0
    demo.theme = theme
    demo.css = custom_css
    return demo