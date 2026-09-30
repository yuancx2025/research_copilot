import { useQuery } from '@tanstack/react-query'
import { ApiError } from '../../../api/client'
import { conversationOptions } from '../queries'
import { conversationView } from '../model/conversation'
import { useUiStore } from '../state/uiStore'
import { useRunStream } from './useRunStream'

const EMPTY_PROGRESS: never[] = []
export function useConversationView(conversationId?: string) {
  const query = useQuery(conversationOptions(conversationId ?? ''))
  const view = conversationView(query.data)
  const reconnect = useRunStream(view.activeRun)
  const stream = useUiStore((state) => view.activeRun ? state.runs[view.activeRun.id] : undefined)
  return {
    ...view, conversationId, streaming: Boolean(view.activeRun),
    progress: stream?.progress ?? EMPTY_PROGRESS, streamNotice: stream?.notice ?? null,
    reconnect, canReconnect: Boolean(stream?.notice),
    loading: Boolean(conversationId) && query.isPending,
    missing: query.error instanceof ApiError && query.error.status === 404,
    error: query.error, refetch: query.refetch,
  }
}
