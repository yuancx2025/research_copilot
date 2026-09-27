import { apiFetch, getJson, sendJson, setCsrfToken } from './client'
import { readEventStream } from './sse'
import type {
  AppConfig,
  Draft,
  ExportResult,
  LastResearch,
  NotionPage,
  NotionStatus,
  ResearchEvent,
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

export async function startResearch(message: string, onEvent: (event: ResearchEvent) => void) {
  const response = await apiFetch('/api/research', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ message }),
  })
  await readEventStream(response, onEvent)
}

export async function followResearch(onEvent: (event: ResearchEvent) => void) {
  await readEventStream(await apiFetch('/api/research/events'), onEvent)
}

export const fetchLastResearch = () => getJson<LastResearch>('/api/research/last')

export const resetSession = () => sendJson<void>('/api/session/reset', 'POST')

export const previewStudyPlan = () => sendJson<Draft>('/api/study-plan/preview', 'POST')

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
