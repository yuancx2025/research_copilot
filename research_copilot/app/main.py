"""
Research Copilot - Main Application Entry Point

This module serves as the primary entry point for the Research Copilot application.
It initializes the Gradio UI and launches the web interface.
"""
from research_copilot.ui.gradio_app import create_gradio_ui


def main():
    """
    Main entry point for the Research Copilot application.
    
    Initializes the Gradio interface and launches the web server.
    """
    demo = create_gradio_ui()
    print("\n🚀 Launching Research Copilot...")
    print("📍 Open http://127.0.0.1:7860 in your browser")
    # Pass theme and css to launch() for Gradio 6.0+
    demo.launch(theme=demo.theme, css=demo.css)


if __name__ == "__main__":
    main()
