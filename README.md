# Research Copilot

A local, single-user research assistant that searches local documents, academic papers, the web, GitHub, YouTube, and a connected Notion workspace. After research, you can preview a study plan and export that exact draft to a Notion page you choose.

The UI is a React app in `[frontend/](frontend/)` (see [frontend/README.md](frontend/README.md)) served by the same FastAPI process that exposes the JSON/SSE API under `/api`. Notion OAuth binds to `127.0.0.1` only.

## Architecture

```mermaid
flowchart TD
    Start[User Query] --> Summarize[Summarize Conversation History]
    Summarize --> AnalyzeRewrite[Analyze and Rewrite Query]

    AnalyzeRewrite -->|Query Unclear| HumanInput[Request Clarification]
    HumanInput --> AnalyzeRewrite

    AnalyzeRewrite -->|Query Clear| ClassifyIntent[Classify Research Intent]

    ClassifyIntent --> Router{Intent Router}

    Router -->|ArXiv| ArXivAgent[ArXiv Agent]
    Router -->|YouTube| YouTubeAgent[YouTube Agent]
    Router -->|GitHub| GitHubAgent[GitHub Agent]
    Router -->|Web| WebAgent[Web Agent]
    Router -->|Local Docs| LocalAgent[Local RAG Agent]
    Router -->|Notion notes| NotionAgent[Notion Agent]

    ArXivAgent --> Aggregate[Aggregate Results]
    YouTubeAgent --> Aggregate
    GitHubAgent --> Aggregate
    WebAgent --> Aggregate
    LocalAgent --> Aggregate
    NotionAgent --> Aggregate

    Aggregate --> End[Return Response]
    End --> Preview[Preview Study Plan]
    Preview --> Export[Export displayed draft]

    style ClassifyIntent fill:#4a9eff,stroke:#2d5f9f,color:#ffffff
    style Router fill:#ff6b6b,stroke:#c92a2a,color:#ffffff
    style Aggregate fill:#51cf66,stroke:#2f9e44,color:#ffffff
    style NotionAgent fill:#9775fa,stroke:#6741d9,color:#ffffff
    style Export fill:#9775fa,stroke:#6741d9,color:#ffffff
```



**How a request runs**

- The orchestrator classifies intent against **currently available sources**. Notion is offered only while a workspace connection is active.
- Specialized agents run in parallel. Notion research tools are read-only search and fetch.
- Citations from Notion require a fetched page (title, URL, and content). Search hits alone are not treated as evidence.
- Study-plan publishing is not part of the research graph. Preview generates a draft; Export publishes the displayed Markdown without generating again.
- Research runs stream progress to the browser over Server-Sent Events (sources selected, each agent finishing, then the answer).

**Backend layout**

```
research_copilot/
├── app/             # FastAPI factory, /api routers, SSE, security, OAuth routes, static serving
├── orchestrator/    # LangGraph routing, intent, aggregation
├── sources/         # One package per source (agent + tools + citations)
│   ├── notion/      # Notion research, MCP, REST publish, OAuth identity
│   ├── github|web|arxiv|youtube|local/
├── runtime/         # Agents, toolkits, MCP, OAuth lifecycle, source registry
├── study_plans/     # Draft generation (Notion only publishes)
├── rag/             # Chunking, retrieval, reranking, document ingest
├── storage/         # Qdrant, parent store, encrypted credentials, export ledger
├── db/              # SQLAlchemy models, repositories, Alembic migrations
├── core/            # RAGSystem, ChatInterface, ResearchService (saved runs and drafts)
└── config/          # Shared local/GCP settings, including MCP
```



## Features

- **Local RAG**: upload PDF and Markdown files and query them
- **ArXiv, web, GitHub, YouTube**: specialized research agents
- **Notion research**: search and fetch notes from one OAuth-connected workspace
- **Preview then export**: generate a study plan, inspect the Markdown, choose a destination page, then publish
- **Saved conversations**: messages, results, citations, and study-plan previews in PostgreSQL, with explicit retry after an interrupted run
- **Local OAuth**: Connect/Disconnect in the Research tab; tokens are encrypted in PostgreSQL with a key file outside the repository



## Quick start



### Prerequisites

- Python 3.11 (compatibility baseline for this MCP stack)
- Node.js 20+ to build the frontend (see [frontend/README.md](frontend/README.md) for UI development)
- A PostgreSQL database. Local development uses a Neon **direct** endpoint (`sslmode=require`, hostname without `-pooler`)
- API keys for the LLM and any non-Notion sources you enable



### Installation

`pyproject.toml` pins the tested Python 3.11 baseline: MCP 1.25.0, `langchain-mcp-adapters` 0.2.1, LangChain 1.2.0, LangChain Core 1.2.6, and LangGraph 1.0.5. Keep MCP below v2.

```bash
conda create -n research311 python=3.11 -y
conda activate research311
pip install -e ".[test]"
```

Optional GCP extras:

```bash
pip install -e ".[gcp,test]"
```

### Configuration

Create a `.env` file:

```bash
# LLM
GOOGLE_API_KEY=your-google-gemini-api-key
LLM_PROVIDER=google
LLM_MODEL=gemini-2.5-flash

# Other research sources
TAVILY_API_KEY=your-tavily-api-key
GITHUB_TOKEN=your-github-token

# Neon direct endpoint (not the pooled host). Required in every mode.
DATABASE_URL=postgresql://USER:PASSWORD@ep-example.c-13.us-east-1.aws.neon.tech/research_copilot?sslmode=require

# Notion: mcp (OAuth research + export), rest (legacy token export), or disabled
NOTION_BACKEND=mcp
OAUTH_BASE_URL=http://127.0.0.1:7860

# Optional. Defaults to ~/.config/research-copilot/credential-keys.json
# MCP_CREDENTIAL_KEY_FILE=

# REST compatibility mode only (never used as an OAuth fallback)
# NOTION_BACKEND=rest
# NOTION_API_KEY=your-notion-integration-token
# NOTION_PARENT_PAGE_ID=your-parent-page-uuid

# Optional GitHub/web MCP stdio servers
# USE_GITHUB_MCP=true
# GITHUB_MCP_COMMAND=npx,-y,@modelcontextprotocol/server-github
# USE_WEB_SEARCH_MCP=false
```

`OAUTH_BASE_URL` must be `http://127.0.0.1:<port>` with no path. Hosted multi-user OAuth is out of scope for this release.

### Launch

Apply the schema, then create the credential key once. The server refuses to start against an unmigrated database and never generates a replacement key:

```bash
research-copilot-admin db upgrade
research-copilot-admin keys init
```

`db upgrade` creates the application tables and LangGraph's checkpoint tables. `keys init` writes a random 32-byte key to `~/.config/research-copilot/credential-keys.json` (mode `0600`, directory `0700`) and refuses to overwrite an existing file.

Build the frontend once, then start the server. Both entrypoints use the same FastAPI application factory:

```bash
cd frontend && npm install && npm run build && cd ..
python -m research_copilot.app.main
# or
python app.py
```

Open `http://127.0.0.1:7860`. The old `/ui` path redirects there.

For Vite hot reload, proxy behavior, and frontend file layout, see [frontend/README.md](frontend/README.md).

## Using Notion

1. Set `NOTION_BACKEND=mcp` and start the app on `127.0.0.1`.
2. In the Research tab, click **Connect Notion** and complete consent in the new tab. The tab closes itself when the connection finishes.
3. Restarting the app reuses the encrypted credentials while the grant remains valid. You should not see another consent screen until access expires or you disconnect. Switching onto this store needs one fresh Notion authorization; existing macOS Keychain tokens are not imported. After the new connection works, the old Keychain item can be removed with `security delete-generic-password -s research-copilot.notion-mcp`.
4. Ask a question that needs your notes (for example, “what did I write about MCP in Notion”). Ordinary research still works while disconnected.
5. After citations exist, click **Preview Study Plan**, search or paste a destination page, then **Export displayed plan**. The preview is saved before it is shown, and export publishes that stored Markdown.
6. **Disconnect** stops credential use immediately and deletes the encrypted payload. Saved answers, citations, and previews stay readable; drafts from the old connection cannot be exported. Disconnect is reported as failed if the database update fails. Revoke the grant in Notion settings if you also want the provider-side authorization removed.



### Credential key backup

The key file is the only copy of the encryption key. It is not stored in Neon, source control, frontend bundles, or database backups. Copy it to a protected place (an encrypted password manager or another machine you control) before you rely on the Notion connection.

If the file is missing, unreadable, or is a different key, Notion stays disconnected with an error that names the file. Research history in PostgreSQL remains available. Restore the original file, or run **Connect Notion** again to create a new encrypted credential. Do not run `keys init` over a file you still need: it will refuse, and deleting the file first makes every saved credential undecryptable.

OAuth failures never fall back to `NOTION_API_KEY`. REST export remains an explicit `NOTION_BACKEND=rest` compatibility mode that still uses the block renderer.

## Known limitations

- One local profile and one active Notion workspace connection
- OAuth is loopback-only (`127.0.0.1`); no hosted multi-user OAuth
- macOS Keychain is required for OAuth; there is no plaintext credential fallback
- Notion research is read-only; page creation is the Export button
- Export is not exactly-once across network failures. A timeout after dispatch is recorded as unknown and is not retried automatically. Inspect Notion before creating another page.
- Local disconnect does not revoke the Notion grant
- Persistent Notion research caching is disabled; connection-dependent in-memory results are cleared on disconnect or workspace change
- The visible transcript is kept in the browser tab's session storage; the server keeps only conversation context in memory, and a server restart clears it
- One research request runs at a time; Chat and Research share the same conversation
- Dynamic subagent spawning, general workspace editing, shared database storage, distributed refresh, cloud deployment, and a newer MCP stack are follow-up work

