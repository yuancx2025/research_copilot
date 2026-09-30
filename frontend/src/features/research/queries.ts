import { queryOptions, type QueryClient } from '@tanstack/react-query'
import { fetchConversation, listConversations } from '../../api/endpoints/conversations'
import { fetchRun } from '../../api/endpoints/research'
import { ApiError } from '../../api/client'
import { ContractError } from '../../api/validation'

export const researchKeys = {
  all: ['research'] as const,
  lists: () => ['research', 'conversations'] as const,
  details: () => ['research', 'conversation'] as const,
  detail: (id: string) => ['research', 'conversation', id] as const,
  run: (id: string) => ['research', 'run', id] as const,
  submission: (id: string) => ['research', 'submission', id] as const,
}
export const retryRead = (count: number, error: Error) =>
  count < 1 && !(error instanceof ContractError) && !(error instanceof ApiError && error.status < 500)
export const conversationListOptions = () => queryOptions({
  queryKey: researchKeys.lists(), queryFn: ({ signal }) => listConversations(signal), retry: retryRead,
})
export const conversationOptions = (id: string) => queryOptions({
  queryKey: researchKeys.detail(id), queryFn: ({ signal }) => fetchConversation(id, signal), enabled: Boolean(id), retry: retryRead,
})
export const runOptions = (id: string) => queryOptions({
  queryKey: researchKeys.run(id), queryFn: ({ signal }) => fetchRun(id, signal), retry: retryRead,
})
export async function refreshConversation(client: QueryClient, id: string) {
  await Promise.all([
    client.invalidateQueries({ queryKey: researchKeys.detail(id) }),
    client.invalidateQueries({ queryKey: researchKeys.lists() }),
  ])
}
