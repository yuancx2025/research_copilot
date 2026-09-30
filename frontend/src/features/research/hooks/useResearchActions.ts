import { useIsMutating, useMutation, useQueryClient, type QueryClient } from '@tanstack/react-query'
import { ContractError } from '../../../api/validation'
import { ApiError } from '../../../api/client'
import { replyToRun, submitRun } from '../../../api/endpoints/research'
import type { ConversationDetail, Run } from '../../../api/types'
import { useUiStore } from '../state/uiStore'
import { replaceRun } from '../model/conversation'
import { researchKeys, refreshConversation } from '../queries'

export interface Submission { conversationId: string; text: string; replyTo?: string; retryOf?: string }
interface Attempt { fingerprint: string; requestId: string; pending?: Promise<Run> }
// QueryClient lifetime, not module-global server state. Retain IDs for ambiguous retries.
const attempts = new WeakMap<QueryClient, Map<string, Attempt>>()
export function submitResearch(client: QueryClient, input: Submission): Promise<Run> {
  let byConversation = attempts.get(client)
  if (!byConversation) { byConversation = new Map(); attempts.set(client, byConversation) }
  const message = input.text.trim()
  if (!message && !input.retryOf) return Promise.reject(new Error('Enter a research question.'))
  const fingerprint = JSON.stringify([message, input.replyTo, input.retryOf])
  const previous = byConversation.get(input.conversationId)
  if (previous?.pending) {
    return previous.fingerprint === fingerprint ? previous.pending : Promise.reject(new Error('A message is already being submitted.'))
  }
  const attempt: Attempt = previous?.fingerprint === fingerprint ? previous : { fingerprint, requestId: crypto.randomUUID() }
  byConversation.set(input.conversationId, attempt)
  attempt.pending = (async () => {
    let run: Run
    try {
      run = input.replyTo ? await replyToRun(input.replyTo, message, attempt.requestId)
        : await submitRun(input.conversationId, message, attempt.requestId, input.retryOf)
    } catch (error) {
      if (error instanceof ApiError && error.status === 409 && /already running/i.test(error.message)) {
        throw new ApiError(409, 'Another research run is active. Your message is saved here; submit it after that run finishes.')
      }
      throw error
    }
    if (run.conversation_id !== input.conversationId || (input.replyTo && run.id !== input.replyTo)) throw new ContractError('submission ownership')
    client.setQueryData(researchKeys.run(run.id), run)
    client.setQueryData<ConversationDetail>(researchKeys.detail(input.conversationId), (detail) => replaceRun(detail, run))
    if (!input.retryOf && useUiStore.getState().drafts[input.conversationId] === input.text) {
      useUiStore.getState().setDraft(input.conversationId, '')
    }
    byConversation.delete(input.conversationId)
    void refreshConversation(client, input.conversationId)
    return run
  })().finally(() => { attempt.pending = undefined })
  return attempt.pending
}

export function useResearchActions(conversationId: string) {
  const client = useQueryClient()
  const mutation = useMutation({
    mutationKey: researchKeys.submission(conversationId),
    mutationFn: (input: Omit<Submission, 'conversationId'>) => submitResearch(client, { ...input, conversationId }),
    retry: false,
  })
  const pending = useIsMutating({ mutationKey: researchKeys.submission(conversationId) }) > 0
  return { ...mutation, pending }
}
