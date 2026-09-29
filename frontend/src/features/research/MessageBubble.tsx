import { Markdown } from '../../components/Markdown'
import type { ConversationMessage } from '../../api/types'

export function MessageBubble({ message }: { message: ConversationMessage }) {
  return (
    <div className={`message ${message.role}`} data-role={message.role}>
      {message.role === 'assistant' ? <Markdown>{message.content}</Markdown> : <p>{message.content}</p>}
      {message.clarification && <span className="badge">Reply to clarify</span>}
    </div>
  )
}
