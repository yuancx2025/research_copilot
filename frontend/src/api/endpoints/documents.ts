import { apiFetch, getJson, sendJson } from '../client'
import { zDocumentsOut, zUploadEventOut } from '../contracts/generated/zod.gen'
import { readEventStream } from '../sse'
import type { UploadEvent } from '../types'
export const listDocuments = (signal?: AbortSignal) => getJson('/api/documents', zDocumentsOut, signal)
export const clearDocuments = () => sendJson('/api/documents', 'DELETE', zDocumentsOut)
export async function uploadDocuments(files: File[], onEvent: (event: UploadEvent) => void, signal?: AbortSignal) {
  const body = new FormData()
  files.forEach((file) => body.append('files', file, file.name))
  const response = await apiFetch('/api/documents', { method: 'POST', body, signal })
  await readEventStream(response, zUploadEventOut, onEvent, signal)
}
