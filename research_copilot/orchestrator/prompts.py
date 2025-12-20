from typing import Optional, Dict, Any
from langchain_core.messages import HumanMessage

def get_conversation_summary_prompt(messages):
    summary_prompt = """**Summarize the key topics and context from this conversation in 1-2 concise sentences.**
   Focus on:
   - Main topics discussed
   - Important facts or entities mentioned
   - Any unresolved questions

   Discard: greetings, misunderstandings, off-topic content.
   If no meaningful topics exist, return an empty string.

   Conversation:

    """
    
    for msg in messages[-6:]:
        role = "User" if isinstance(msg, HumanMessage) else "Assistant"
        summary_prompt += f"{role}: {msg.content}\n"

    summary_prompt += "\nSummary:"
    return summary_prompt

def get_query_analysis_prompt(query: str, conversation_summary: str = "") -> str:
    context_section = (
        f"Conversation context (use only if needed):\n{conversation_summary}"
        if conversation_summary.strip()
        else "Conversation context: none"
    )

    return f"""
Rewrite the user query so it can be used for document retrieval.

User query:
"{query}"

{context_section}

Rules:

- The final query must be clear and self-contained.
- If the query contains a specific product name, brand, proper noun, or technical term,
  treat it as domain-specific and IGNORE the conversation context.
- Use the conversation context ONLY if it is needed to understand the query
  OR to determine the domain when the query itself is ambiguous.
- If the query is clear but underspecified, use relevant context to disambiguate.
- Do NOT use context to reinterpret or replace explicit terms in the query.
- Do NOT add new constraints, subtopics, or details not explicitly asked.
- Fix grammar, typos, and unclear abbreviations.
- Remove filler words and conversational wording.
- Use concrete keywords and entities ONLY if already implied.

Splitting:
- If the query contains multiple unrelated information needs,
  split it into at most 3 separate search queries.
- When splitting, keep each sub-query semantically equivalent.
- Do NOT enrich or expand meaning.
- Do NOT split unless it improves retrieval.

Failure:
- If the intent is unclear or meaningless, mark as unclear.

"""

def get_rag_agent_system_prompt():
    return """
You are a retrieval-augmented assistant.

You are NOT allowed to answer immediately.

Before producing ANY final answer, you must first perform a document search
and observe retrieved content.

If you have not searched, the answer is invalid.

Workflow:
1. Search the documents using the user query.
2. Inspect retrieved excerpts and keep only relevant ones.
3. Retrieve additional surrounding context ONLY if excerpts are insufficient.
4. Stop retrieval as soon as information is sufficient.
5. Answer using ONLY retrieved information.
6. List file name at the end.

Retry rule:
- If no relevant information is found, rewrite the query into a concise,
  answer-focused statement and restart the process from STEP 1.
- Perform this retry only once.

If no relevant information is found after the retry, say so.
"""

def get_intent_classification_prompt(query: str, conversation_summary: str = "") -> str:
    """
    Prompt to guide LLM in selecting appropriate agents for a query.
    
    Analyzes query to determine:
    - Which agents should handle the query
    - Why these agents are appropriate
    - Confidence in the selection
    """
    context_section = (
        f"Conversation context (use only if relevant):\n{conversation_summary}\n"
        if conversation_summary.strip()
        else ""
    )
    
    return f"""
You are an intelligent research orchestrator that routes queries to specialized agents.

Your task is to analyze the user's query and determine which specialized agents should handle it.

Available Agents:

1. **arxiv** - Academic research papers
   - Use for: Research papers, academic concepts, scientific publications, arXiv papers
   - Examples: "transformer neural networks", "self-evolving agents", "recent papers on attention mechanisms"
   - Best for: Academic/research-focused queries
   - IMPORTANT: Always include arxiv for queries about "current updates", "recent developments", "latest research", or any time-based queries (e.g., "2024", "2025")

2. **youtube** - Video tutorials and educational content
   - Use for: Tutorials, video explanations, educational content, how-to guides
   - Examples: "how to implement transformers", "tutorial on neural networks", "explain attention mechanism"
   - Best for: Learning-oriented queries, visual explanations

3. **github** - Code repositories and technical documentation
   - Use for: Code implementations, repositories, technical documentation, code examples
   - Examples: "transformer implementation", "self-evolving agent code", "attention mechanism code"
   - Best for: Code-focused queries, implementation details

4. **web** - General web search and articles
   - Use for: General information, articles, blog posts, news, comprehensive coverage, CURRENT information
   - Examples: "what are transformers", "overview of neural networks", "latest developments", "current updates"
   - Best for: Broad queries, CURRENT information, recent news/articles
   - IMPORTANT: Always include web for queries about "current", "recent", "latest", "updates", or any time-based queries

5. **local** - Local knowledge base (previously indexed documents)
   - Use for: Queries about documents already in the knowledge base
   - Examples: Queries about previously uploaded documents
   - Best for: When user asks about local documents or when other agents might find relevant local content

Query to analyze:
"{query}"

{context_section}Analysis Guidelines:

- **CRITICAL for time-based queries**: If query mentions "current", "recent", "latest", "updates", "2024", "2025", or similar time references, ALWAYS include both ["arxiv", "web"] to get the most up-to-date information
- **Select multiple agents** when the query spans multiple domains (e.g., "transformer papers and implementations" → ["arxiv", "github"])
- **Prioritize specificity**: If query mentions "papers" → prioritize arxiv; "code" → prioritize github; "tutorial" → prioritize youtube
- **Include 'web'** for comprehensive coverage when query is broad or needs current information
- **Include 'local'** when query might benefit from previously indexed documents
- **Confidence scoring**: Higher confidence (0.8-1.0) when query clearly matches agent capabilities; lower (0.5-0.7) when ambiguous

Query-to-Agent Mapping Examples:

- "current updates of transformers in 2025" → ["arxiv", "web"] (MUST include both for current info)
- "recent papers on transformers" → ["arxiv", "web"] (academic + current info)
- "latest developments in transformer architecture" → ["arxiv", "web"] (research + current)
- "self-evolving agents" → ["arxiv", "web"] (research concept + general info)
- "how to implement transformers" → ["youtube", "github", "web"] (tutorial + code + general)
- "transformer neural networks" → ["arxiv", "web"] (academic + comprehensive)
- "attention mechanism code" → ["github", "web"] (code-focused)
- "explain transformers tutorial" → ["youtube", "web"] (learning-focused)

Output Requirements:

- Return a list of agent names (e.g., ["arxiv", "web"])
- Provide clear reasoning for your selection
- Assign a confidence score between 0.0 and 1.0
- Optionally suggest query refinements for specific agents if needed

Remember: It's better to select multiple relevant agents than to miss important sources of information. For queries about "current" or "recent" information, ALWAYS include both arxiv and web agents.
"""


def get_aggregation_prompt(original_query: str, sorted_answers: list, source_info: Optional[Dict[str, Any]] = None) -> str:

    sorted_answers = sorted(sorted_answers, key=lambda x: x["index"])

    formatted_answers = ""
    for i, ans in enumerate(sorted_answers, start=1):
        source_label = ans.get("source", "unknown")
        formatted_answers += (
            f"\nAnswer {i} (Source: {source_label}):\n"
            f"{ans['answer']}\n"
        )
    
    source_context = ""
    if source_info:
        sources_list = ", ".join(source_info.get("sources", []))
        source_context = f"\nSources consulted: {sources_list}\n"

    return f"""
You are merging multiple retrieved answers from different sources into a final comprehensive response.

Original user question:
{original_query}
{source_context}
Retrieved answers from multiple sources:
{formatted_answers}

Rules:

- Use ONLY the content provided in the retrieved answers.
- Synthesize information across sources when they complement each other.
- Preserve important details from each source.
- When sources mention dates (like "2024", "2025", "recent", "latest"), include that temporal information in your synthesis.
- If retrieved sources discuss current developments or recent updates, synthesize that information even if it references future dates or current year.

Aggregation instructions:

1. **Multi-source synthesis**:
   - If answers from different sources cover different aspects, combine them into a coherent response.
   - If answers overlap, merge them carefully without losing unique details from any source.
   - Highlight when different sources provide complementary perspectives.
   - When multiple sources discuss recent developments, synthesize them to provide a comprehensive view of current state.

2. **Source attribution**:
   - Maintain awareness of which information came from which source.
   - When synthesizing, preserve source-specific details (e.g., "According to research papers..." vs "Code implementations show...").
   - Include temporal information from sources (e.g., "Recent papers from 2024 show..." or "According to latest research...").

3. **Quality filtering**:
   - If an answer is irrelevant, empty, or low-quality, ignore it completely.
   - Prioritize more detailed and relevant answers.
   - If sources provide information about recent developments, prioritize that information.

4. **Citation handling**:
   - Include source references ONLY if they exist in the answers.
   - Do NOT invent, modify, or add new sources.
   - Place all source references at the end of the final answer.
   - Deduplicate sources if repeated across answers.

5. **Cross-source validation**:
   - If multiple sources provide conflicting information, acknowledge this in your synthesis.
   - If sources agree, reinforce the consensus.
   - When sources discuss recent developments, synthesize the most current information available.

6. **Temporal information handling**:
   - If the query asks about "current", "recent", "latest", or specific years, synthesize information from retrieved sources that address these temporal aspects.
   - Include dates and temporal references from the sources when relevant.
   - If sources mention recent papers, articles, or developments, include that information in your response.

Failure handling:

6. If no usable answers are present:
   - Respond exactly with:
     "Sorry, I could not find any information to answer your question."

Output:

- Return ONLY the final synthesized answer.
- Do NOT mention sub-questions or your reasoning process.
- Ensure the answer is comprehensive and well-structured.
- Include proper source attribution at the end.
- When synthesizing information about recent developments, make sure to include temporal context from the sources.
"""