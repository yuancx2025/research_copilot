import { apiFetch, getJson, sendJson } from '../client'
import { zRunOut, zResearchEventOut } from '../contracts/generated/zod.gen'
import { readEventStream } from '../sse'
import type { ResearchEvent } from '../types'
import type { RunCreate, ReplyCreate } from '../contracts/generated/types.gen'
export const fetchRun = (id: string, signal?: AbortSignal) => getJson(`/api/runs/${encodeURIComponent(id)}`, zRunOut, signal)
export const submitRun = (conversationId: string, message: string, requestId: string, retryOfRunId?: string) =>
  sendJson(`/api/conversations/${encodeURIComponent(conversationId)}/runs`, 'POST', zRunOut, {
    message, request_id: requestId, retry_of_run_id: retryOfRunId ?? null,
  } satisfies RunCreate)
export const replyToRun = (runId: string, message: string, requestId: string) =>
  sendJson(`/api/runs/${encodeURIComponent(runId)}/reply`, 'POST', zRunOut, { message, request_id: requestId } satisfies ReplyCreate)
export async function followRun(runId: string, after: number, onEvent: (event: ResearchEvent) => void, signal?: AbortSignal) {
  const response = await apiFetch(`/api/runs/${encodeURIComponent(runId)}/events?after=${after}`, { signal })
  await readEventStream(response, zResearchEventOut, onEvent, signal)
}
