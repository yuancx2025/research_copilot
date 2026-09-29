# Research Copilot — Frontend

React + TypeScript single-page app for Research Copilot. It talks to the same FastAPI process as the backend over `/api` (JSON and Server-Sent Events) and `/oauth/notion` (local Notion OAuth).

In production the backend serves the built assets from `dist/`. In development, Vite runs on port 5173 and proxies API traffic to the backend.

## What it does

| Route | Purpose |
|-------|---------|
| `/research/:conversationId?` | Research chat, live progress, citations and sources sidebar, Notion connect bar, study plan preview/export, compact document upload |
| `/chat/:conversationId?` | The same selected conversation, without the artifacts sidebar |
| `/documents` | Upload PDF/Markdown into the knowledge base, list and clear documents |
| `/oauth/done` | Shown after Notion consent; tries to close the OAuth tab |

**State model (single user, one browser profile):**

- **Conversations, messages, runs, citations, and study-plan drafts** — PostgreSQL, loaded with TanStack Query. Chat and Research are two views of the selected conversation.
- **Unsent composer text** — Zustand, persisted under `sessionStorage` key `research-copilot:v2`. Older `research-copilot` snapshots are left in place and are not treated as saved research.
- **Notion connection status** — TanStack Query polling `/oauth/notion/status`. A generation change refreshes conversation queries so stale previews stop being exportable.
- **Document list** — TanStack Query on `/api/documents`; uploads stream progress over SSE and update the cache.

**Research flow:** `Composer` → `POST /api/conversations/{id}/runs` (202, with a client request id) → `GET /api/runs/{id}/events?after=<seq>`. A clarification reply goes to `POST /api/runs/{id}/reply`. Opening a conversation reattaches to a queued or running run by id. **New conversation** keeps previous history.

## Prerequisites

- Node.js 20+
- Backend running on `http://127.0.0.1:7860` (see the [root README](../README.md))

Use `127.0.0.1`, not `localhost`, when using Notion MCP OAuth.

## Commands

```bash
npm install
npm run dev        # http://127.0.0.1:5173 — proxies /api and /oauth/notion to :7860
npm run build      # output to dist/ (served by FastAPI in production)
npm test           # Vitest
npm run typecheck
```

For OAuth to return to the dev server after consent, set in the repo `.env`:

```bash
FRONTEND_URL=http://127.0.0.1:5173
```

The Notion redirect URI stays on the backend port (`OAUTH_BASE_URL`); only the post-callback landing page uses `FRONTEND_URL`.

The dev proxy rewrites the `Origin` header to match `OAUTH_BASE_URL` so the backend same-origin write check still passes ([`vite.config.ts`](vite.config.ts)).

## File structure

```
frontend/
├── index.html              # Shell; React mounts at #root
├── vite.config.ts          # Dev server, API proxy, Vitest
├── package.json
├── tsconfig.json
├── public/
│   └── favicon.svg
└── src/
    ├── main.tsx            # QueryClient, BrowserRouter, global styles
    ├── App.tsx             # Nav, routes, config load, recoverResearch on startup
    │
    ├── api/                # HTTP only (no UI)
    │   ├── client.ts       # fetch wrapper, in-memory CSRF, retry once on 403
    │   ├── endpoints.ts    # Functions per backend route
    │   ├── sse.ts          # Parse SSE from POST response bodies
    │   ├── types.ts        # JSON/SSE TypeScript types
    │   └── *.test.ts
    │
    ├── store/
    │   └── researchStore.ts   # Messages, result, draft, streaming, send/clear/recover
    │
    ├── hooks/
    │   ├── useAppConfig.ts       # GET /api/config
    │   └── useNotionConnection.ts  # OAuth status, connect/disconnect, generation sync
    │
    ├── features/
    │   ├── documents/      # DocumentsPage, UploadDropzone, DocumentList
    │   ├── research/       # ResearchPage, ChatPage, ChatThread, Composer,
    │   │                   # MessageBubble, ProgressTimeline, ArtifactsPanel
    │   └── notion/         # NotionConnectionBar, StudyPlanPanel, DestinationPicker,
    │                       # OAuthDonePage
    │
    ├── components/
    │   └── Markdown.tsx    # react-markdown + remark-gfm
    │
    ├── lib/
    │   ├── citations.ts    # Grouping and labels for citation UI
    │   └── progress.ts     # Human-readable SSE progress steps
    │
    ├── styles/
    │   ├── tokens.css      # Theme variables (ported from legacy Gradio CSS)
    │   └── global.css      # Layout and components
    │
    └── test/               # Vitest setup and HTTP helpers
```

### Where logic lives

| Concern | Primary files |
|---------|----------------|
| Submit research / SSE handling | `store/researchStore.ts`, `api/endpoints.ts`, `api/sse.ts` |
| Citations UI | `features/research/ArtifactsPanel.tsx`, `lib/citations.ts` |
| Notion OAuth UI | `features/notion/NotionConnectionBar.tsx`, `hooks/useNotionConnection.ts` |
| Study plan preview/export | `features/notion/StudyPlanPanel.tsx`, `DestinationPicker.tsx` |
| Document upload (SSE progress) | `features/documents/UploadDropzone.tsx` |
| CSRF for writes | `api/client.ts` (token from `/api/config` and `/oauth/notion/status`) |

Backend API shapes are documented on the running server at `/docs` (OpenAPI). Types in `api/types.ts` should stay aligned with those schemas.

## Tests

Component and library tests use Vitest and Testing Library; API client tests mock `fetch`. Run from this directory:

```bash
npm test
```

Python integration tests for `/api` live under `tests/app/` in the repo root.
