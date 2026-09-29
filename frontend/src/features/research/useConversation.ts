import { useQuery } from '@tanstack/react-query'
import { useParams } from 'react-router-dom'
import { fetchConversation } from '../../api/endpoints'
import { useRunRecovery, useUiStore } from '../../store/researchStore'
import type { Draft, ResearchResult, Run } from '../../api/types'

export function useConversationView() {
  const { conversationId } = useParams()
  const conversation = useQuery({
    queryKey: ['conversation', conversationId],
    queryFn: () => fetchConversation(conversationId!),
    enabled: Boolean(conversationId),
  })
  useRunRecovery(conversation.data)
  const streaming = useUiStore((state) => Boolean(state.streamingRunId))
  const progress = useUiStore((state) => state.progress)
  const streamNotice = useUiStore((state) => state.streamNotice)
  const runs = conversation.data?.runs ?? []
  const latest = runs.at(-1) ?? null
  const resultRun = [...runs].reverse().find((run) => run.result && run.status !== 'superseded') ?? null
  const draft = [...(conversation.data?.drafts ?? [])].reverse().find((item) => item.run_id === resultRun?.id) ?? null
  const retryable = latest && (latest.status === 'interrupted' || latest.status === 'failed') ? latest : null
  const replyTo = latest?.status === 'awaiting_clarification' ? latest : null
  return {
    conversationId,
    messages: conversation.data?.messages ?? [],
    streaming,
    progress,
    streamNotice,
    result: (resultRun?.result ?? null) as ResearchResult | null,
    resultRun: resultRun as Run | null,
    draft: draft as Draft | null,
    retryable,
    replyTo,
    loading: Boolean(conversationId) && conversation.isLoading,
  }
}
