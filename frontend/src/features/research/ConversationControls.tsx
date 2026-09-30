import { useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useLocation, useNavigate, useParams } from 'react-router-dom'
import { createConversation, listConversations } from '../../api/endpoints'

export function ConversationControls() {
  const { conversationId } = useParams()
  const navigate = useNavigate()
  const location = useLocation()
  const queryClient = useQueryClient()
  const section = location.pathname.startsWith('/chat') ? 'chat' : 'research'
  const conversations = useQuery({ queryKey: ['conversations'], queryFn: ({ signal }) => listConversations(signal) })
  const [error, setError] = useState<string | null>(null)

  const open = (id: string) => {
    if (id) navigate(`/${section}/${id}`)
  }

  const create = async () => {
    setError(null)
    try {
      const created = await createConversation()
      await queryClient.invalidateQueries({ queryKey: ['conversations'] })
      navigate(`/${section}/${created.id}`)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not start a conversation.')
    }
  }

  return (
    <div className="conversation-select">
      <label>
        Conversation
        <select
          aria-label="Conversation"
          value={conversationId ?? ''}
          onChange={(event) => open(event.target.value)}
        >
          {!conversationId && <option value="">Select a conversation</option>}
          {(conversations.data ?? []).map((conversation) => (
            <option key={conversation.id} value={conversation.id}>
              {conversation.title}
            </option>
          ))}
        </select>
      </label>
      <button type="button" onClick={create}>
        New conversation
      </button>
      {error && <p className="notice error">{error}</p>}
    </div>
  )
}
