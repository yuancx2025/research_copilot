// Mirrors research_copilot/app/schemas.py and the SSE events emitted by the API.

export type NotionBackend = 'disabled' | 'rest' | 'mcp'

export interface AppConfig {
  notion_backend: NotionBackend
  default_destination: string
  sources: string[]
  csrf: string | null
}

export interface Citation {
  source_type: string
  title: string
  url: string
  snippet: string
  authors: string[]
  date: string | null
  channel: string | null
  repo: string | null
}

export interface ResearchResult {
  query: string
  answer: string
  citations: Citation[]
  sources: Record<string, number>
  needs_clarification: boolean
  can_preview_plan: boolean
  generation: string | null
}

export interface LastResearch {
  running: boolean
  result: ResearchResult | null
}

export interface ProgressEvent {
  type: 'progress'
  node: string
  agents?: string[]
  source?: string
  clear?: boolean
}

export interface ErrorEvent {
  type: 'error'
  message: string
}

export type ResearchEvent = ProgressEvent | ({ type: 'result' } & ResearchResult) | ErrorEvent

export interface UploadResult {
  added: number
  skipped: number
  documents: string[]
}

export type UploadEvent =
  | { type: 'progress'; fraction: number; message: string }
  | ({ type: 'result' } & UploadResult)
  | ErrorEvent

export interface Draft {
  draft_id: string
  title: string
  markdown: string
}

export interface NotionPage {
  title: string
  ref: string
}

export interface ExportResult {
  status: 'success' | 'failure' | 'unknown' | 'pending'
  page_id: string | null
  url: string | null
  message: string
  retryable: boolean
}

export type ConnectionState = 'connected' | 'connecting' | 'disconnected' | 'reconnect_required' | 'failed'

export interface NotionStatus {
  status: ConnectionState
  workspace: string
  generation: string | null
  error: string | null
  csrf: string
}
