import gradio as gr
from research_copilot.core.chat_interface import ChatInterface
from research_copilot.core.document_manager import DocumentManager
from research_copilot.core.rag_system import RAGSystem
from research_copilot.ui.research_formatter import format_citations_markdown, format_agent_results_summary
from research_copilot.ui.css import custom_css
from research_copilot.config import settings as config
import logging
import asyncio
from research_copilot.notion.export_service import generate_draft
from research_copilot.notion.schemas import StudyPlanDraft

logger = logging.getLogger(__name__)


def is_notion_configured():
    return getattr(config, 'NOTION_BACKEND', 'disabled') in ('rest', 'mcp')


def create_gradio_ui(notion_service=None, export_service=None):
    rag_system = RAGSystem()
    rag_system.initialize()
    rag_system.notion_service = notion_service
    operation_lock = asyncio.Lock()
    
    doc_manager = DocumentManager(rag_system)
    chat_interface = ChatInterface(rag_system)
    
    # Store last research data for study plan creation
    last_research_data = {}
    last_query = ""
    research_generation = None
    
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
    
    async def chat_handler(msg, hist):
        """Handler for Chat tab - returns only the answer string."""
        async with operation_lock:
            answer, research_data = await chat_interface.chat(msg, hist)
        # gr.ChatInterface manages history automatically, so just return the answer
        return answer
    
    async def research_chat_handler(msg, hist):
        """Handler for Research tab that returns both answer and artifacts."""
        nonlocal last_research_data, last_query, research_generation
        
        async with operation_lock:
            answer, research_data = await chat_interface.chat(msg, hist)
            # Store only completed research while holding the invocation lock.
            last_research_data = research_data.copy()
            last_research_data["answer_text"] = answer
            last_query = msg.strip()
            research_generation = notion_service.connection.generation if notion_service else "rest"
        
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
        
        values = (formatted_hist, citations_markdown, sources_summary)
        return (*values, gr.update(interactive=notion_button_enabled)) if is_notion_configured() else values
    
    def clear_chat_handler():
        chat_interface.clear_session()
    
    def clear_research_handler():
        nonlocal last_research_data, last_query
        chat_interface.clear_session()
        last_research_data = {}
        last_query = ""
        values = ([], "*No citations yet.*", "*No sources used yet.*")
        return (*values, gr.update(interactive=False)) if is_notion_configured() else values
    
    async def invalidate_connection_data():
        nonlocal last_research_data, last_query, research_generation
        last_research_data = {}
        last_query = ""
        research_generation = None
        rag_system._mcp_prepared = False
        rag_system.reset_thread()
        rag_system.agent_graph = None
        rag_system._graph_generation = None

    if notion_service:
        notion_service.connection.listeners.append(invalidate_connection_data)

    async def preview_plan():
        try:
            generation = notion_service.connection.generation if notion_service else "rest"
            if notion_service and not notion_service.connection.connected:
                raise ValueError("Connect Notion first.")
            if not last_research_data or research_generation != generation:
                raise ValueError("Run research with the current connection first.")
            draft = await generate_draft(last_research_data, last_query, rag_system.llm, config, generation or "disconnected")
            if notion_service and (not notion_service.connection.connected or generation != notion_service.connection.generation):
                raise ValueError("Connection changed while generating the preview.")
            return draft.model_dump(), draft.markdown, "", gr.update(interactive=True)
        except Exception:
            return None, "", "Could not generate a draft. Run research with the current connection first.", gr.update(interactive=False)

    async def search_destinations(query):
        if not notion_service:
            return gr.update(choices=[])
        try:
            data = await notion_service.search(query)
            pages = data.get("results", [])
            choices = [(p.get("title", "Untitled"), p.get("url") or p.get("id")) for p in pages if p.get("url") or p.get("id")]
            return gr.update(choices=choices, value=None)
        except Exception:
            gr.Warning("Could not search destinations. Check your Notion connection.")
            return gr.update(choices=[], value=None)

    async def export_plan(draft_data, destination):
        if not draft_data or not export_service:
            return "Generate a preview first.", gr.update(interactive=False)
        try:
            result = await export_service.publish(StudyPlanDraft.model_validate(draft_data), destination)
            if result.status == "success":
                return f"Created: [{result.page_id}]({result.url})", gr.update(interactive=False)
            if result.status == "pending":
                return result.message, gr.update(interactive=False)
            return result.message, gr.update(interactive=result.status == "failure")
        except Exception:
            return "Export could not complete. Check the connection and destination.", gr.update(interactive=True)

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
            gr.Markdown("Explore papers, videos, repositories, web articles, and your connected Notion notes.")
            if notion_service:
                gr.HTML('<iframe src="/oauth/notion/panel" title="Notion connection" style="width:100%;height:90px;border:0"></iframe>')
            
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
                            "Preview Study Plan",
                            variant="primary",
                            size="md",
                            interactive=False,
                            elem_id="notion-study-plan-btn"
                        )
                        
                        draft_state = gr.State(None)
                        preview = gr.Markdown()
                        destination_query = gr.Textbox(label="Search destination pages")
                        destination_search = gr.Button("Search pages")
                        destination_choices = gr.Dropdown(label="Matching pages", choices=[])
                        destination = gr.Textbox(label="Destination page URL or UUID", value=getattr(config, "NOTION_PARENT_PAGE_ID", "") or "")
                        export_button = gr.Button("Export displayed plan", interactive=False)
                        destination_search.click(search_destinations, inputs=destination_query, outputs=destination_choices)
                        destination_choices.change(lambda value: value or "", inputs=destination_choices, outputs=destination)
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
            async def submit_research(msg, hist):
                return await research_chat_handler(msg, hist)
            
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
                    preview_plan,
                    outputs=[draft_state, preview, notion_status, export_button]
                )
    
            if is_notion_configured():
                export_button.click(lambda: gr.update(interactive=False), outputs=export_button).then(
                    export_plan, inputs=[draft_state, destination], outputs=[notion_status, export_button])

    # Attach theme and css to demo for Gradio 6.0
    demo.theme = theme
    demo.css = custom_css
    return demo
