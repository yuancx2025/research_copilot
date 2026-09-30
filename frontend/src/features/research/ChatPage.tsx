import styles from './research.module.css'
import { useParams } from 'react-router-dom'
import { ChatThread } from './components/ChatThread'
import { Composer } from './components/Composer'
import { ConversationControls } from './components/ConversationControls'
import { ConversationStatus } from './components/ConversationStatus'
import { useConversationView } from './hooks/useConversation'
import { useResearchActions } from './hooks/useResearchActions'
export function ChatPage() {
  const { conversationId } = useParams()
  const view = useConversationView(conversationId)
  const action = useResearchActions(conversationId ?? '')
  return <section className={["panel", styles["conversation"], styles["chat-page"]].join(' ')}>
    <ConversationControls />
    <p className="muted">Chat and Research share the selected conversation. Citations appear on the Research tab.</p>
    <ConversationStatus view={view} />
    {!view.loading && !view.error && <>
      <ChatThread placeholder="Ask me anything about your documents…" messages={view.messages}
        streaming={view.streaming} progress={view.progress} retryable={view.retryable} retryPending={action.pending}
        onRetry={() => { if (view.retryable) void action.mutateAsync({ text: '', retryOf: view.retryable.id }).catch(() => {}) }} />
      {action.error && <p className="notice error" role="alert">{action.error.message}</p>}
      <Composer key={conversationId ?? 'new'} conversationId={conversationId} runActive={view.streaming}
        placeholder="Type a message…" replyTo={view.replyTo} />
    </>}
  </section>
}
