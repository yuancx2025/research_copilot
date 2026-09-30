import { useEffect, useRef } from 'react'
import { useMutation, useQuery, useQueryClient, type QueryClient } from '@tanstack/react-query'
import { disconnectNotion, startNotionAuthorization } from '../../../api/endpoints/notion'
import { researchKeys } from '../../research/queries'
import { studyPlanKeys } from '../../study-plan/queries'
import { notionKeys, notionStatusOptions } from './queries'

const generations = new WeakMap<QueryClient, string | null>()
export function useNotionConnection(enabled: boolean) {
  const client = useQueryClient()
  const status = useQuery(notionStatusOptions(enabled))
  const lock = useRef(false)
  const generation = status.data?.generation
  useEffect(() => {
    if (generation === undefined) return
    if (generations.has(client) && generations.get(client) !== generation) {
      void client.invalidateQueries({ queryKey: researchKeys.details() })
      void client.invalidateQueries({ queryKey: studyPlanKeys.drafts() })
      const previousPages = { queryKey: notionKeys.pages(), predicate: (query: { queryKey: readonly unknown[] }) => query.queryKey[2] !== generation }
      void client.cancelQueries(previousPages)
      client.removeQueries(previousPages)
    }
    generations.set(client, generation)
  }, [client, generation])
  const refresh = () => client.invalidateQueries({ queryKey: notionKeys.status() })
  const authorization = useMutation({ mutationFn: startNotionAuthorization, retry: false, onSettled: refresh })
  const disconnection = useMutation({ mutationFn: disconnectNotion, retry: false, onSettled: refresh })
  const connect = () => {
    if (lock.current) return
    lock.current = true
    authorization.reset()
    disconnection.reset()
    // Open synchronously in the click handler, before awaiting the API.
    const tab = window.open('about:blank', '_blank')
    void authorization.mutateAsync().then(({ authorization_url }) => {
      if (tab) tab.location.href = authorization_url
      else window.location.href = authorization_url
    }).catch(() => { tab?.close() }).finally(() => { lock.current = false })
  }
  const disconnect = () => {
    if (lock.current) return
    lock.current = true
    authorization.reset()
    disconnection.reset()
    void disconnection.mutateAsync().catch(() => {}).finally(() => { lock.current = false })
  }
  return { status: status.data, loading: status.isPending, busy: authorization.isPending || disconnection.isPending,
    actionError: authorization.error?.message ?? disconnection.error?.message ?? status.error?.message ?? null,
    connect, disconnect }
}
