import type { QueryClient } from '@tanstack/react-query'
import { fetchRun, followRun } from '../../../api/endpoints/research'
import type { ConversationDetail, Run } from '../../../api/types'
import { ContractError } from '../../../api/validation'
import { isActive, replaceRun } from '../model/conversation'
import { researchKeys, refreshConversation } from '../queries'
import { acceptEvent, ensureProgress, updateProgress } from '../state/uiStore'

function delay(signal: AbortSignal) {
  return new Promise<void>((resolve, reject) => {
    const abort = () => { clearTimeout(timer); reject(signal.reason) }
    const timer = setTimeout(() => { signal.removeEventListener('abort', abort); resolve() }, 2000)
    signal.addEventListener('abort', abort, { once: true })
    if (signal.aborted) abort()
  })
}

// One invocation owns one subscription. Its signal also owns fallback polling.
export async function followSelectedRun(client: QueryClient, run: Pick<Run, 'id' | 'conversation_id'>, signal: AbortSignal): Promise<void> {
  const saved = ensureProgress(run.id, run.conversation_id)
  updateProgress(run.id, { connection: 'connecting', notice: null })
  let notice = 'The progress connection ended. Checking saved research status.'
  try {
    await followRun(run.id, saved.lastSeq, (event) => {
      signal.throwIfAborted()
      acceptEvent(run.id, run.conversation_id, event)
    }, signal)
  } catch (error) {
    if (signal.aborted) return
    notice = error instanceof ContractError ? error.message : 'The progress stream disconnected. Checking saved research status.'
  }
  while (!signal.aborted) {
    try {
      const current = await fetchRun(run.id, signal)
      signal.throwIfAborted()
      if (current.id !== run.id || current.conversation_id !== run.conversation_id) throw new ContractError('run ownership')
      client.setQueryData(researchKeys.run(run.id), current)
      if (!isActive(current.status)) {
        updateProgress(run.id, { connection: 'settled', notice: null })
        client.setQueryData<ConversationDetail>(researchKeys.detail(run.conversation_id), (detail) => replaceRun(detail, current))
        await refreshConversation(client, run.conversation_id)
        return
      }
      updateProgress(run.id, { connection: 'polling', notice: `${notice} Research is still running.` })
    } catch {
      if (signal.aborted) return
      updateProgress(run.id, { connection: 'polling', notice: 'Could not check saved research. Retrying the connection; research may still be running.' })
    }
    try { await delay(signal) } catch { return }
  }
}
