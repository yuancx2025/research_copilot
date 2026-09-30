import styles from '../research.module.css'
import { useRef } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useLocation, useNavigate, useParams } from 'react-router-dom'
import { conversationListOptions } from '../queries'
import { useCreateConversation } from '../hooks/useCreateConversation'

export function ConversationControls() {
  const { conversationId } = useParams()
  const navigate = useNavigate()
  const location = useLocation()
  const section = location.pathname.startsWith('/chat') ? 'chat' : 'research'
  const conversations = useQuery(conversationListOptions())
  const creation = useCreateConversation()
  const lock = useRef(false)
  const create = async () => {
    if (lock.current) return
    lock.current = true
    try { const created = await creation.mutateAsync(); navigate(`/${section}/${created.id}`) }
    catch { /* Mutation error is rendered below. */ }
    finally { lock.current = false }
  }
  return <div className={styles["conversation-select"]}>
    <label>Conversation
      <select aria-label="Conversation" value={conversationId ?? ''}
        onChange={(event) => event.target.value && navigate(`/${section}/${event.target.value}`)}>
        {!conversationId && <option value="">Select a conversation</option>}
        {(conversations.data ?? []).map((conversation) => <option key={conversation.id} value={conversation.id}>{conversation.title}</option>)}
      </select>
    </label>
    <button type="button" onClick={create} disabled={creation.isPending}>{creation.isPending ? 'Creating…' : 'New conversation'}</button>
    {(creation.error || conversations.error) && <p className="notice error" role="alert">{creation.error?.message ?? 'Could not load conversation history.'}</p>}
  </div>
}
