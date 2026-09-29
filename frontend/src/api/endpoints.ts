import { apiFetch, getJson, sendJson, setCsrfToken } from './client'
import { readEventStream } from './sse'
import type {
  AppConfig,
  Conversation,
  ConversationDetail,
  Draft,
  ExportResult,
  NotionPage,
  NotionStatus,
  ResearchEvent,
  Run,
  UploadEvent,
} from './types'

export async function fetchConfig(): Promise<AppConfig> {
  const config = await getJson<AppConfig>('/api/config')
  setCsrfToken(config.csrf)
  return config
}

export const listDocuments = () => getJson<{ documents: string[] }>('/api/documents')

export const clearDocuments = () => sendJson<{ documents: string[] }>('/api/documents', 'DELETE')

export async function uploadDocuments(files: File[], onEvent: (event: UploadEvent) => void) {
  const body = new FormData()
  files.forEach((file) => body.append('files', file, file.name))
  const response = await apiFetch('/api/documents', { method: 'POST', body })
  await readEventStream(response, onEvent)
}

export const listConversations = () => getJson<Conversation[]>('/api/conversations')

export const createConversation = () => sendJson<Conversation>('/api/conversations', 'POST', {})

export const fetchConversation = (id: string) => getJson<ConversationDetail>(`/api/conversations/${id}`)

export const fetchRun = (id: string) => getJson<Run>(`/api/runs/${id}`)

export const submitRun = (conversationId: string, message: string, requestId: string, retryOfRunId?: string) =>
  sendJson<Run>(`/api/conversations/${conversationId}/runs`, 'POST', {
    message,
    request_id: requestId,
    retry_of_run_id: retryOfRunId ?? null,
  })

export const replyToRun = (runId: string, message: string, requestId: string) =>
  sendJson<Run>(`/api/runs/${runId}/reply`, 'POST', { message, request_id: requestId })

export async function followRun(runId: string, after: number, onEvent: (event: ResearchEvent) => void, signal?: AbortSignal) {
  await readEventStream(await apiFetch(`/api/runs/${runId}/events?after=${after}`, { signal }), onEvent)
}

export const previewStudyPlan = (runId: string) => sendJson<Draft>('/api/study-plan/preview', 'POST', { run_id: runId })

export const fetchDraft = (id: string) => getJson<Draft>(`/api/study-plan/drafts/${id}`)

export const exportStudyPlan = (draftId: string, destination: string) =>
  sendJson<ExportResult>('/api/study-plan/export', 'POST', { draft_id: draftId, destination })

export const searchNotionPages = (query: string) =>
  getJson<NotionPage[]>(`/api/notion/pages?q=${encodeURIComponent(query)}`)

export async function fetchNotionStatus(): Promise<NotionStatus> {
  const status = await getJson<NotionStatus>('/oauth/notion/status')
  setCsrfToken(status.csrf)
  return status
}

export const startNotionAuthorization = () =>
  sendJson<{ authorization_url: string }>('/oauth/notion/start', 'POST')

export const disconnectNotion = () =>
  sendJson<{ status: string; message: string }>('/oauth/notion/disconnect', 'POST')
