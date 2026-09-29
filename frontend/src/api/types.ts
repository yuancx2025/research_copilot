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
  run_id: string
  query: string
  answer: string
  citations: Citation[]
  sources: Record<string, number>
  needs_clarification: boolean
  can_preview_plan: boolean
  generation: string | null
}

export type RunStatus =
  | 'queued'
  | 'running'
  | 'awaiting_clarification'
  | 'completed'
  | 'failed'
  | 'interrupted'
  | 'superseded'

export interface Run {
  id: string
  conversation_id: string
  request_id: string
  status: RunStatus
  query: string
  retry_of_run_id: string | null
  error: string | null
  last_seq: number
  created_at: string
  finished_at: string | null
  result: ResearchResult | null
}

export interface ConversationMessage {
  id: string
  role: 'user' | 'assistant' | 'error'
  content: string
  clarification: boolean
  run_id: string | null
  request_id: string | null
  created_at: string
}

export interface Conversation {
  id: string
  title: string
  created_at: string
  updated_at: string
}

export interface ConversationDetail extends Conversation {
  messages: ConversationMessage[]
  runs: Run[]
  drafts: Draft[]
}

export interface ProgressEvent {
  type: 'progress'
  node: string
  seq?: number
  run_id?: string
  agents?: string[]
  source?: string
  clear?: boolean
}

export interface ErrorEvent {
  type: 'error'
  message: string
}

export type ResearchEvent =
  | ProgressEvent
  | { type: 'result'; seq: number; run_id: string; run: Run }
  | (ErrorEvent & { seq?: number; run_id?: string; status?: string })

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
  run_id: string
  title: string
  markdown: string
  exportable: boolean
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
