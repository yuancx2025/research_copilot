import os

# Load environment variables from .env file (if present)
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    # python-dotenv not installed, skip .env loading
    pass

import gradio as gr
from research_copilot.ui.css import custom_css
from research_copilot.ui.gradio_app import create_gradio_ui

if __name__ == "__main__":
    demo = create_gradio_ui()
    print("\n🚀 Launching RAG Assistant...")
    
    # Configure for Cloud Run
    server_name = os.getenv("GRADIO_SERVER_NAME", "0.0.0.0")
    server_port = int(os.getenv("GRADIO_SERVER_PORT", "7860"))
    
    demo.launch(
        server_name=server_name,
        server_port=server_port,
        css=custom_css
    )