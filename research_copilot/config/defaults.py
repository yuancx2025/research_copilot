"""Single source of truth for defaults that several settings modules share."""

# Used when LLM_MODEL is unset. Previously three different defaults existed:
# gcp_settings ("gemini-2.5-flash"), the settings.py fallback ("gemini-3.0-flash") and
# create_llm ("gemini-pro"), so the model depended on which import path ran.
DEFAULT_LLM_MODEL = "gemini-2.5-flash"
DEFAULT_OLLAMA_MODEL = "qwen3:4b-instruct-2507-q4_K_M"
