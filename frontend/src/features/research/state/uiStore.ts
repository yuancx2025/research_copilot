import { create } from 'zustand'
import { createJSONStorage, persist } from 'zustand/middleware'
import type { ProgressEvent, ResearchEvent } from '../../../api/types'
import { ContractError } from '../../../api/validation'

export interface RunProgress {
  conversationId: string
  progress: ProgressEvent[]
  lastSeq: number
  connection: 'idle' | 'connecting' | 'connected' | 'polling' | 'settled'
  notice: string | null
}
interface UiState {
  drafts: Record<string, string>
  runs: Record<string, RunProgress>
  setDraft: (conversationId: string, text: string) => void
}
export const useUiStore = create<UiState>()(persist((set) => ({
  drafts: {}, runs: {},
  setDraft: (id, text) => set((state) => ({ drafts: { ...state.drafts, [id]: text } })),
}), {
  name: 'research-copilot:v2', storage: createJSONStorage(() => sessionStorage),
  partialize: ({ drafts }) => ({ drafts }),
}))

export function ensureProgress(runId: string, conversationId: string): RunProgress {
  const current = useUiStore.getState().runs[runId]
  if (current) {
    if (current.conversationId !== conversationId) throw new ContractError('run ownership')
    return current
  }
  const entry: RunProgress = { conversationId, progress: [], lastSeq: 0, connection: 'idle', notice: null }
  useUiStore.setState((state) => ({ runs: { ...state.runs, [runId]: entry } }))
  return entry
}
export function updateProgress(runId: string, patch: Partial<RunProgress>) {
  useUiStore.setState((state) => {
    const current = state.runs[runId]
    return current ? { runs: { ...state.runs, [runId]: { ...current, ...patch } } } : state
  })
}
export function acceptEvent(runId: string, conversationId: string, event: ResearchEvent): boolean {
  if (event.run_id !== runId || (event.type === 'result' &&
      (event.run.id !== runId || event.run.conversation_id !== conversationId))) {
    throw new ContractError('event run identity')
  }
  const current = ensureProgress(runId, conversationId)
  if (event.seq <= current.lastSeq) return false
  updateProgress(runId, { lastSeq: event.seq, connection: 'connected',
    progress: event.type === 'progress' ? [...current.progress, event] : current.progress })
  return true
}
