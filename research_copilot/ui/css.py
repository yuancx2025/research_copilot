"""Custom CSS styling for Research Copilot Gradio UI"""

custom_css = """
/* ============================================
   MODERN RESEARCH COPILOT THEME
   Clean, readable, professional UI
   ============================================ */

/* ROOT VARIABLES */
:root {
    --bg-primary: #0a0a0a;
    --bg-secondary: #141414;
    --bg-tertiary: #1e1e1e;
    --bg-elevated: #252525;
    --border-color: #333333;
    --border-hover: #444444;
    --text-primary: #f5f5f5;
    --text-secondary: #a0a0a0;
    --text-muted: #666666;
    --accent-blue: #3b82f6;
    --accent-blue-hover: #60a5fa;
    --accent-red: #ef4444;
    --user-bubble: #3b82f6;
    --bot-bubble: #1e1e1e;
    --radius-sm: 8px;
    --radius-md: 12px;
    --radius-lg: 16px;
}

.gradio-container { 
    max-width: 1200px !important;
    width: 100% !important;
    margin: 0 auto !important;
    font-family: -apple-system, BlinkMacSystemFont, 'SF Pro Display', 'Segoe UI', sans-serif !important;
    background: var(--bg-primary) !important;
    color: var(--text-primary) !important;
}

footer { visibility: hidden !important; }
.progress-text { display: none !important; }

/* TYPOGRAPHY */
h1, h2, h3, h4, h5, h6 { color: var(--text-primary) !important; font-weight: 600 !important; }
p, span, label, div { color: var(--text-primary) !important; }

/* TABS */
.tabs { border-bottom: none !important; background: transparent !important; }
.tab-nav { border-bottom: 1px solid var(--border-color) !important; gap: 8px !important; }

button[role="tab"] {
    color: var(--text-secondary) !important;
    border: none !important;
    border-bottom: 2px solid transparent !important;
    background: transparent !important;
    padding: 12px 20px !important;
    font-size: 15px !important;
    transition: all 0.2s ease !important;
}

button[role="tab"]:hover { color: var(--text-primary) !important; }

button[role="tab"][aria-selected="true"] {
    color: var(--text-primary) !important;
    border-bottom: 2px solid var(--accent-blue) !important;
}

/* BUTTONS */
button {
    border-radius: var(--radius-sm) !important;
    font-weight: 500 !important;
    transition: all 0.2s ease !important;
}

.primary { background: var(--accent-blue) !important; color: white !important; }
.primary:hover { background: var(--accent-blue-hover) !important; transform: translateY(-1px) !important; }
.stop { background: var(--accent-red) !important; color: white !important; }

/* CHATBOT - CRITICAL FIX FOR TEXT VISIBILITY */
.chatbot { 
    background: var(--bg-secondary) !important;
    border: 1px solid var(--border-color) !important;
    border-radius: var(--radius-lg) !important;
}

/* User messages */
.user, .message.user, [data-role="user"] {
    background: var(--user-bubble) !important;
    color: white !important;
    padding: 12px 16px !important;
    border-radius: var(--radius-md) !important;
}

.user *, .message.user *, [data-role="user"] * { color: white !important; }

/* Bot messages - WHITE TEXT ON DARK BACKGROUND */
.bot, .message.bot, [data-role="assistant"] {
    background: var(--bg-tertiary) !important;
    color: var(--text-primary) !important;
    border: 1px solid var(--border-color) !important;
    padding: 12px 16px !important;
    border-radius: var(--radius-md) !important;
}

.bot *, .message.bot *, [data-role="assistant"] * { 
    color: var(--text-primary) !important; 
}

/* Ensure all text in chat is visible */
.chatbot p, .chatbot span, .chatbot li, .chatbot div {
    color: inherit !important;
}

/* Code blocks */
.chatbot code {
    background: rgba(0, 0, 0, 0.3) !important;
    padding: 2px 6px !important;
    border-radius: 4px !important;
}

.chatbot pre {
    background: #0d0d0d !important;
    border: 1px solid var(--border-color) !important;
    padding: 12px !important;
    border-radius: var(--radius-sm) !important;
}

/* INPUTS */
textarea, input[type="text"] {
    background: var(--bg-tertiary) !important;
    border: 1px solid var(--border-color) !important;
    border-radius: var(--radius-md) !important;
    color: var(--text-primary) !important;
    font-size: 15px !important;
    padding: 12px 16px !important;
}

textarea:focus, input:focus {
    border-color: var(--accent-blue) !important;
    box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.15) !important;
}

textarea::placeholder, input::placeholder { color: var(--text-muted) !important; }

/* FILE UPLOAD */
.file-preview, [data-testid="file-upload"] {
    background: var(--bg-tertiary) !important;
    border: 2px dashed var(--border-color) !important;
    border-radius: var(--radius-md) !important;
}

.file-preview:hover { border-color: var(--accent-blue) !important; }

/* FILE LIST */
#file-list-box {
    background: var(--bg-tertiary) !important;
    border: 1px solid var(--border-color) !important;
}

#file-list-box textarea {
    background: transparent !important;
    color: var(--text-primary) !important;
    font-family: 'SF Mono', monospace !important;
}

/* RESEARCH ARTIFACTS */
#sources-summary {
    background: var(--bg-tertiary) !important;
    border: 1px solid var(--border-color) !important;
    border-radius: var(--radius-md) !important;
    padding: 16px !important;
}

#sources-summary h3, #sources-summary strong {
    color: var(--accent-blue) !important;
}

#sources-summary p, #sources-summary li {
    color: var(--text-primary) !important;
}

.citations-box, #citations-display {
    background: var(--bg-tertiary) !important;
    border: 1px solid var(--border-color) !important;
    border-radius: var(--radius-md) !important;
    padding: 16px !important;
    max-height: 400px !important;
    overflow-y: auto !important;
}

.citations-box h3, .citations-box strong { color: var(--accent-blue) !important; }
.citations-box p, .citations-box li { color: var(--text-primary) !important; }
.citations-box a { color: var(--accent-blue) !important; text-decoration: none !important; }
.citations-box a:hover { text-decoration: underline !important; }

/* SCROLLBARS */
.citations-box::-webkit-scrollbar, .chatbot::-webkit-scrollbar { width: 6px !important; }
.citations-box::-webkit-scrollbar-thumb, .chatbot::-webkit-scrollbar-thumb {
    background: var(--border-color) !important;
    border-radius: 3px !important;
}

/* PROGRESS BAR */
.progress-bar-wrap { background: var(--bg-tertiary) !important; border-radius: var(--radius-sm) !important; }
.progress-bar { background: var(--accent-blue) !important; }

/* DOCUMENT TAB */
#doc-management-tab { max-width: 600px !important; margin: 0 auto !important; padding: 20px !important; }
"""
