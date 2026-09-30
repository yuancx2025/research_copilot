# Research Copilot — Frontend

React and TypeScript, with TanStack Query for server state, Zustand for composer drafts and temporary progress, and Zod for validating incoming API data. FastAPI serves the production build; Vite proxies API requests during development.

## Development

Use Node.js **22.18 or newer** and the backend dependencies described in the [root README](../README.md). Use `127.0.0.1` for local Notion OAuth.

```bash
npm ci
npm run dev           # http://127.0.0.1:5173; backend defaults to :7860
npm test
npm run typecheck
npm run build         # dist/, served by FastAPI
npm run contracts:check
```

Set `VITE_BACKEND_URL` when starting Vite to use another backend address. For OAuth during development, set `FRONTEND_URL=http://127.0.0.1:5173` in the repository `.env`. The OAuth callback remains on `OAUTH_BASE_URL`; only the final landing page goes to Vite. The proxy rewrites the request origin to the backend origin, preserving the backend's CSRF checks.

The generator is pinned to `@hey-api/openapi-ts` 0.99.0. TypeScript is pinned to 6.0.3 because this generator uses the JavaScript compiler API, which the installed TypeScript 7 package did not expose. Zod and the generator are pinned so upgrades produce deliberate contract diffs. The `js-yaml` override pins its patched transitive dependency.

## Ownership

```text
src/
├── app/                         # Providers, nested routes, shared layout, config
├── api/
│   ├── contracts/generated/     # Generated wire types and Zod schemas
│   ├── endpoints/               # Named endpoint functions, split by resource
│   ├── client.ts                # HTTP errors, CSRF, JSON response validation
│   ├── sse.ts                   # Stream framing and reader cleanup
│   ├── validation.ts            # Friendly contract errors
│   └── types.ts                 # Friendly aliases of generated wire types
├── features/
│   ├── research/
│   │   ├── components/          # Composer, thread, citations, progress, controls
│   │   ├── hooks/               # Submission, selected conversation, stream recovery
│   │   ├── model/               # Pure status, citation and progress helpers
│   │   ├── state/               # Composer drafts and run progress only
│   │   └── queries.ts           # Query keys, reads and invalidation rules
│   ├── documents/              # Upload, clear, list, query definitions
│   ├── integrations/notion/    # Connection, OAuth popup, destination selection
│   └── study-plan/             # Preview, draft and export workflows
├── shared/components/          # Reused Markdown rendering
└── styles/                     # Theme tokens, resets and shared base controls
```

Keep feature-specific code in that feature. Pages compose features through their public exports. Endpoint modules and pure model helpers never import components. Larger features separate components, workflows, state and model helpers; small features stay flat. CSS Modules live beside their owning feature or shared component. Theme tokens and base styles remain global.

The application layout uses an `Outlet`; `/research/:conversationId?`, `/chat/:conversationId?`, and `/documents` keep their existing URLs. `/oauth/done` is standalone and does not wait for application configuration. Research and Chat render the same saved conversation.

## API contracts

The source of truth is [the backend Pydantic schemas](../research_copilot/app/schemas.py). The offline exporter registers the real API routes and OAuth declarations without starting the application, connecting to PostgreSQL or OAuth, or creating a research engine. It includes OAuth even when Notion is disabled locally.

```bash
# From frontend/, after changing backend contract declarations:
npm run contracts:generate
npm run contracts:check

# Optional explicit Python interpreter:
CONTRACT_PYTHON=../.venv-mcp/bin/python npm run contracts:generate

# Standalone export, from the repository root:
.venv-mcp/bin/python -m research_copilot.app.export_contracts --output /tmp/openapi.json
```

Generation writes `contracts/openapi.json` and `src/api/contracts/generated/`. Include both in the same change as the backend declarations; do not edit generated files. The check regenerates in a temporary directory and compares bytes, including obsolete files. Normal development and builds use the checked-in output and do not need a running backend or Python generator.

Only TypeScript types and reusable Zod definitions are generated. Named endpoint functions remain handwritten; there is no extra generated SDK or query layer. Use generated request types when building outgoing bodies and response validators on every JSON read. Frontend-only view models live in feature model/state modules. Serialized dates stay strings and valid timezone offsets are accepted.

SSE endpoints are documented as `text/event-stream`. Their `x-event-schema` points to a named component describing **one decoded event**, not the entire HTTP response. Research and upload streams use separate discriminated event unions. The shared decoder handles chunks, separators and keepalive comments, then validates each payload before delivering it to a feature.

Unknown extra fields are tolerated. Malformed required fields, unsupported variants and invalid JSON raise a `ContractError`, distinct from HTTP errors and network failures. Components show a short actionable message rather than raw Zod diagnostics. Explicit empty-response helpers avoid pretending an empty body is typed JSON. Reads and streams forward cancellation signals, and readers are cancelled/released on completion, error or navigation.

## State and recovery

- **TanStack Query:** saved conversations, runs, document lists, plan drafts, connection status and request lifecycles. Each feature owns its keys and invalidation rules.
- **Zustand:** unsent composer text plus temporary progress keyed by run ID, with conversation ownership and the last consumed sequence. Only drafts persist in `sessionStorage` under `research-copilot:v2`. Older `research-copilot` snapshots are left untouched.
- **Feature controllers:** submission, clarification replies, explicit retries, subscriptions and reconciliation. Pure functions derive the latest usable result and display state.

Only the selected conversation's active run has a progress subscription. Navigation aborts that subscription and any fallback polling; it does not cancel backend research. Returning resumes after the last event this browser actually consumed. A browser reload discards temporary progress and replays from sequence zero. The server's `last_seq` is never substituted for the browser's cursor. Duplicate sequences are ignored, incorrect run IDs are rejected, and obsolete subscriptions cannot change the selected view.

After a terminal stream event, the controller fetches the saved run and refreshes the conversation detail and list. If the stream ends unexpectedly or contains invalid data, it checks the saved run and polls every two seconds while the run remains active. A visible **Reconnect progress** action replaces polling with a new subscription. A lost connection never marks research finished. Conversation hooks distinguish loading, missing history and failed requests; failed loads do not render empty conversations.

Submissions have an immediate duplicate guard, retain the request ID when retrying the same attempt, and retain composer text on rejection. Acceptance clears only the text that was submitted, preserving later edits. A global busy response explains that another research run is active and keeps the draft. The backend still permits only one active research run across the application.

Uploads validate their own events and refresh the document list. Plan previews refresh saved conversation/draft data. A changed Notion connection generation invalidates conversation/draft data and discards destination results belonging to older generations. The connect click opens its popup synchronously before awaiting the authorization URL.

Writes do not automatically retry on network or contract errors. The existing one-time CSRF refresh on an explicit 403 remains. A lost or malformed export response produces an **unknown outcome** and disables resubmission for that draft during the application session, including feature unmount/remount. Check Notion before taking further export action; the backend export ledger remains authoritative across reloads.

## Verification

Frontend tests cover API validation, nullable/default fields, timezone offsets, SSE framing and cleanup, scoped navigation, Strict Mode cleanup, replay cursors, reconnection/polling, duplicate submissions, busy responses, clarification replies, retained drafts, load failures, uploads, preview/export, CSRF and Notion generation changes.

Run the affected backend tests from the repository root:

```bash
.venv-mcp/bin/python -m pytest tests/app -q -o addopts='' --tb=short
```

The API tests require the dedicated `TEST_DATABASE_URL`. Their fixtures create and remove a temporary schema. Contract-only tests also verify deterministic export and representative backend payloads without requiring PostgreSQL:

```bash
.venv-mcp/bin/python -m pytest tests/app/test_contracts.py -q -o addopts=''
```

For browser acceptance against a configured backend:

1. Start research in one conversation, switch to another, then return. Check scoped progress, ongoing backend activity, and replay without duplicates.
2. Reload during research. Progress should reconstruct from the beginning.
3. Interrupt the progress connection while leaving the API reachable. Research remains active, polling reports saved completion, and **Reconnect progress** resumes from the consumed cursor.
4. Check a rejected/busy submission retains text, clarification replies resume the correct run, and failed loads show a recoverable error.
5. Upload a document, preview a plan, and exercise Notion connection changes. Verify uncertain exports are not automatically resubmitted.

Mocked tests and a scripted research engine do not establish live model, document-indexing, OAuth-provider or Notion export behavior. Record those live checks separately.

### Refactor verification (2026-09-29)

The frontend suite, TypeScript checking, production build and contract-drift check passed. The affected backend API/contract suite passed against the dedicated test database.

Browser checks used the production frontend build, real FastAPI routes and PostgreSQL in a temporary test schema, with a scripted research engine. Verified conversation switching, scoped progress, resuming after sequence 2, reload replay from sequence 0, retained text on a global busy response, explicit reconnect, completion through fallback polling, saved answers/citations, and Chat/Documents navigation. No browser console errors were observed. The server was stopped and its temporary schema removed afterward.

Live model research, document indexing, provider OAuth consent and Notion publishing were not exercised in that browser check. The production build still reports Vite's advisory for a JavaScript chunk above 500 kB; this does not fail the build.
