import styles from './notion.module.css'
import type { NotionStatus } from '../../../api/types'
import { useNotionConnection } from './useNotionConnection'

function describe(status: NotionStatus | undefined, loading: boolean): string {
  if (loading || !status) return 'Checking Notion connection…'
  switch (status.status) {
    case 'connected':
      return status.workspace ? `Connected to ${status.workspace}` : 'Connected'
    case 'connecting':
      return 'Waiting for consent in the Notion tab…'
    case 'reconnect_required':
      return 'Notion access expired. Reconnect to keep using your notes.'
    case 'failed':
      return status.error ?? 'Notion connection failed.'
    default:
      return status.error ?? 'Notion is not connected.'
  }
}

export function NotionConnectionBar() {
  const { status, loading, busy, actionError, connect, disconnect } = useNotionConnection(true)
  const state = status?.status
  const linked = state === 'connected' || state === 'reconnect_required'
  return (
    <div className={`${styles['connection-bar']} ${state ? styles[state] ?? '' : ''}`}>
      <span className={styles["connection-dot"]} aria-hidden />
      <span className={styles["connection-text"]}>{actionError ?? describe(status, loading)}</span>
      {state !== 'connected' && (
        <button onClick={connect} disabled={busy || loading || state === 'connecting'}>
          {state === 'reconnect_required' ? 'Reconnect Notion' : 'Connect Notion'}
        </button>
      )}
      {linked && (
        <button onClick={disconnect} disabled={busy}>
          Disconnect
        </button>
      )}
    </div>
  )
}
