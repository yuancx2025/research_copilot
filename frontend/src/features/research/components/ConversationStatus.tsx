import type { useConversationView } from '../hooks/useConversation'
export function ConversationStatus({ view }: { view: ReturnType<typeof useConversationView> }) {
  if (view.loading) return <p className="muted" role="status">Loading conversation…</p>
  if (view.error) return <div className="notice error" role="alert">
    <p>{view.missing ? 'This conversation could not be found.' : `Could not load this conversation. ${view.error.message}`}</p>
    <button onClick={() => void view.refetch()}>Reload conversation</button>
  </div>
  if (view.streamNotice) return <div className="notice error" role="status">
    <p>{view.streamNotice}</p>
    {view.canReconnect && <button onClick={view.reconnect}>Reconnect progress</button>}
  </div>
  return null
}
