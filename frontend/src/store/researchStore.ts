import { useEffect } from 'react'
import type { QueryClient } from '@tanstack/react-query'
import { useQueryClient } from '@tanstack/react-query'
import { create } from 'zustand'
import { createJSONStorage, persist } from 'zustand/middleware'
import { fetchRun, followRun, replyToRun, submitRun } from '../api/endpoints'
import type { ConversationDetail, ProgressEvent, ResearchEvent, Run } from '../api/types'

interface UiState {
  drafts: Record<string, string>
  streamingRunId: string | null
  progress: ProgressEvent[]
  streamNotice: string | null
  setDraft: (conversationId: string, text: string) => void
}

// Only unsent composer text is persisted. Saved research lives in PostgreSQL.
// The legacy `research-copilot` session key is never read.
export const useUiStore = create<UiState>()(
  persist(
    (set) => ({
      drafts: {},
      streamingRunId: null,
      progress: [],
      streamNotice: null,
      setDraft: (conversationId, text) =>
        set((state) => ({ drafts: { ...state.drafts, [conversationId]: text } })),
    }),
    {
      name: 'research-copilot:v2',
      storage: createJSONStorage(() => sessionStorage),
      partialize: ({ drafts }) => ({ drafts }),
    },
  ),
)

export function requestId(): string {
  return crypto.randomUUID()
}

export function takeEvent(seen: Set<number>, event: { seq?: number }): boolean {
  if (event.seq == null || seen.has(event.seq)) return false
  seen.add(event.seq)
  return true
}

const inflight = new Map<string, Promise<void>>()

export function followSavedRun(queryClient: QueryClient, run: Run): Promise<void> {
  const existing = inflight.get(run.id)
  if (existing) return existing
  const promise = consume(queryClient, run).finally(() => {
    if (inflight.get(run.id) === promise) inflight.delete(run.id)
  })
  inflight.set(run.id, promise)
  return promise
}

async function consume(queryClient: QueryClient, run: Run) {
  const store = useUiStore
  store.setState({ streamingRunId: run.id, progress: [], streamNotice: null })
  const seen = new Set<number>()
  try {
    await followRun(run.id, run.last_seq, (event: ResearchEvent) => {
      if (!takeEvent(seen, event) || event.type !== 'progress') return
      store.setState((state) => ({ progress: [...state.progress, event] }))
    })
  } catch (error) {
    try {
      const current = await fetchRun(run.id)
      if (current.status === 'queued' || current.status === 'running') {
        store.setState({ streamNotice: 'The progress stream disconnected. Research is still running.' })
      }
    } catch {
      store.setState({ streamNotice: error instanceof Error ? error.message : 'The progress stream disconnected.' })
    }
  } finally {
    if (store.getState().streamingRunId === run.id) store.setState({ streamingRunId: null, progress: [] })
    await queryClient.invalidateQueries({ queryKey: ['conversation', run.conversation_id] })
  }
}

export async function sendMessage(queryClient: QueryClient, conversationId: string, text: string, replyTo?: Run) {
  const message = text.trim()
  if (!message || useUiStore.getState().streamingRunId) return
  const run = replyTo
    ? await replyToRun(replyTo.id, message, requestId())
    : await submitRun(conversationId, message, requestId())
  await queryClient.invalidateQueries({ queryKey: ['conversation', conversationId] })
  await followSavedRun(queryClient, run)
}

export async function retryRun(queryClient: QueryClient, conversationId: string, runId: string) {
  if (useUiStore.getState().streamingRunId) return
  const run = await submitRun(conversationId, '', requestId(), runId)
  await queryClient.invalidateQueries({ queryKey: ['conversation', conversationId] })
  await followSavedRun(queryClient, run)
}

export function useRunRecovery(detail: ConversationDetail | undefined) {
  const queryClient = useQueryClient()
  const running = detail?.runs.find((run) => run.status === 'queued' || run.status === 'running')
  useEffect(() => {
    if (running) void followSavedRun(queryClient, running)
  }, [queryClient, running])
}
