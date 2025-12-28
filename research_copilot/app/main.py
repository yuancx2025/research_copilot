"""
Research Copilot - Main Application Entry Point

This module serves as the primary entry point for the Research Copilot application.
It initializes the Gradio UI and launches the web interface.
"""
import os

# Load environment variables from .env file (if present)
# This must happen before importing any modules that use configuration
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    # python-dotenv not installed, skip .env loading
    pass

from research_copilot.ui.gradio_app import create_gradio_ui


def main():
    """
    Main entry point for the Research Copilot application.
    
    Initializes the Gradio interface and launches the web server.
    """
    demo = create_gradio_ui()
    print("\n🚀 Launching Research Copilot...")
    
    # Configure for Cloud Run
    server_name = os.getenv("GRADIO_SERVER_NAME", "0.0.0.0")
    server_port = int(os.getenv("GRADIO_SERVER_PORT", "7860"))
    
    print(f"📍 Server will be available at http://{server_name}:{server_port}")
    
    # Pass theme and css to launch() for Gradio 6.0+
    demo.launch(
        server_name=server_name,
        server_port=server_port,
        theme=demo.theme,
        css=demo.css
    )


if __name__ == "__main__":
    main()
