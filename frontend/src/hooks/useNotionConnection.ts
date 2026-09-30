import { useEffect, useRef, useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { disconnectNotion, fetchNotionStatus, startNotionAuthorization } from '../api/endpoints'
export function useNotionConnection(enabled: boolean) {
  const queryClient = useQueryClient()
  const [actionError, setActionError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  const status = useQuery({
    queryKey: ['notion-status'],
    queryFn: ({ signal }) => fetchNotionStatus(signal),
    enabled,
    refetchInterval: (query) => (query.state.data?.status === 'connecting' ? 2000 : 10000),
    refetchOnWindowFocus: true,
  })

  const generation = status.data?.generation
  const seenGeneration = useRef<string | null | undefined>(undefined)
  useEffect(() => {
    if (generation === undefined && !status.data) return
    if (seenGeneration.current !== undefined && seenGeneration.current !== (generation ?? null)) {
      void queryClient.invalidateQueries({ queryKey: ['conversation'] })
    }
    if (status.data) seenGeneration.current = generation ?? null
  }, [status.data, generation, queryClient])

  const refresh = () => queryClient.invalidateQueries({ queryKey: ['notion-status'] })

  // Must run synchronously inside the click handler: opening the tab after an
  // await would be treated as a pop-up and blocked.
  const connect = async () => {
    setActionError(null)
    setBusy(true)
    const tab = window.open('about:blank', '_blank')
    try {
      const { authorization_url } = await startNotionAuthorization()
      if (tab) tab.location.href = authorization_url
      else window.location.href = authorization_url
    } catch (error) {
      tab?.close()
      setActionError(error instanceof Error ? error.message : 'Could not start authorization.')
    } finally {
      setBusy(false)
      refresh()
    }
  }

  const disconnect = async () => {
    setActionError(null)
    setBusy(true)
    try {
      await disconnectNotion()
    } catch {
      setActionError('Could not remove the connection. Check the database and retry.')
    } finally {
      setBusy(false)
      refresh()
    }
  }

  return { status: status.data, loading: status.isLoading, busy, actionError, connect, disconnect }
}
