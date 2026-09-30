import { useEffect, useState } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import type { Run } from '../../../api/types'
import { followSelectedRun } from './runSubscription'
import { updateProgress, useUiStore } from '../state/uiStore'

export function useRunStream(run: Run | null) {
  const client = useQueryClient()
  const [attempt, setAttempt] = useState(0)
  const id = run?.id
  const conversationId = run?.conversation_id
  useEffect(() => {
    if (!id || !conversationId) return
    const controller = new AbortController()
    void followSelectedRun(client, { id, conversation_id: conversationId }, controller.signal).catch(() => {
      if (!controller.signal.aborted) updateProgress(id, { connection: 'idle', notice: 'Could not follow this research run. Reconnect to try again.' })
    })
    return () => {
      controller.abort()
      if (useUiStore.getState().runs[id]?.connection !== 'settled') updateProgress(id, { connection: 'idle' })
    }
    // Re-fetching the same run must not restart the subscription.
  }, [client, id, conversationId, attempt])
  return () => setAttempt((value) => value + 1)
}
