import { create } from 'zustand'
import { createJSONStorage, persist } from 'zustand/middleware'
import { ApiError } from '../api/client'
import { fetchLastResearch, followResearch, resetSession, startResearch } from '../api/endpoints'
import type { Draft, ProgressEvent, ResearchEvent, ResearchResult } from '../api/types'

export interface ChatMessage {
  id: string
  role: 'user' | 'assistant' | 'error'
  content: string
  clarification?: boolean
}

interface ResearchState {
  // The backend keeps conversation context, but prunes messages after each question,
  // so the visible transcript lives here.
  messages: ChatMessage[]
  result: ResearchResult | null
  draft: Draft | null
  generation: string | null | undefined
  pendingQuery: string | null
  progress: ProgressEvent[]
  streaming: boolean
  apply: (event: ResearchEvent) => void
  setDraft: (draft: Draft | null) => void
  syncGeneration: (generation: string | null) => void
  clearLocal: () => void
}

let nextId = 0
const messageId = () => `${Date.now()}-${nextId++}`

export const useResearchStore = create<ResearchState>()(
  persist(
    (set) => ({
      messages: [],
      result: null,
      draft: null,
      generation: undefined,
      pendingQuery: null,
      progress: [],
      streaming: false,
      apply: (event) =>
        set((state) => {
          if (event.type === 'progress') return { progress: [...state.progress, event] }
          if (event.type === 'error') {
            return {
              pendingQuery: null,
              result: null,
              messages: [...state.messages, { id: messageId(), role: 'error', content: event.message }],
            }
          }
          const { type: _type, ...result } = event
          return {
            pendingQuery: null,
            result,
            draft: null,
            messages: [
              ...state.messages,
              { id: messageId(), role: 'assistant', content: result.answer, clarification: result.needs_clarification },
            ],
          }
        }),
      setDraft: (draft) => set({ draft }),
      syncGeneration: (generation) =>
        set((state) => {
          if (state.generation === undefined || state.generation === generation) return { generation }
          return { generation, result: null, draft: null }
        }),
      clearLocal: () => set({ messages: [], result: null, draft: null, pendingQuery: null, progress: [] }),
    }),
    {
      name: 'research-copilot',
      storage: createJSONStorage(() => sessionStorage),
      partialize: ({ messages, result, draft, generation, pendingQuery }) => ({
        messages,
        result,
        draft,
        generation,
        pendingQuery,
      }),
    },
  ),
)

async function consume(stream: (onEvent: (event: ResearchEvent) => void) => Promise<void>) {
  const store = useResearchStore
  store.setState({ streaming: true, progress: [] })
  let settled = false
  try {
    await stream((event) => {
      if (event.type !== 'progress') settled = true
      store.getState().apply(event)
    })
    if (!settled) store.getState().apply({ type: 'error', message: 'The research stream ended unexpectedly.' })
  } catch (error) {
    const message = error instanceof Error ? error.message : 'Research could not start.'
    if (!settled) store.getState().apply({ type: 'error', message })
  } finally {
    store.setState({ streaming: false, progress: [] })
  }
}

export async function sendMessage(text: string) {
  const message = text.trim()
  const store = useResearchStore
  if (!message || store.getState().streaming) return
  store.setState((state) => ({
    pendingQuery: message,
    messages: [...state.messages, { id: messageId(), role: 'user', content: message }],
  }))
  await consume((onEvent) => startResearch(message, onEvent))
}

// After a reload, reattach to a run that is still going or pick up one that
// finished while the page was away.
export async function recoverResearch() {
  const store = useResearchStore
  if (store.getState().streaming) return
  let last
  try {
    last = await fetchLastResearch()
  } catch {
    return
  }
  const { pendingQuery } = store.getState()
  if (last.running) {
    await consume(followResearch)
  } else if (pendingQuery) {
    if (last.result?.query === pendingQuery) store.getState().apply({ type: 'result', ...last.result })
    else store.getState().apply({ type: 'error', message: 'The request was interrupted. Send it again.' })
  } else if (!store.getState().result && last.result) {
    store.setState({ result: last.result })
  }
}

export async function clearConversation(): Promise<string | null> {
  try {
    await resetSession()
  } catch (error) {
    if (error instanceof ApiError && error.status === 409) return error.message
    throw error
  }
  useResearchStore.getState().clearLocal()
  return null
}
