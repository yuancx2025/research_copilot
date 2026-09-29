import { useQueryClient } from '@tanstack/react-query'
import { retryRun } from '../../store/researchStore'
import { ChatThread } from './ChatThread'
import { Composer } from './Composer'
import { ConversationControls } from './ConversationControls'
import { useConversationView } from './useConversation'

export function ChatPage() {
  const queryClient = useQueryClient()
  const view = useConversationView()
  return (
    <section className="panel conversation chat-page">
      <ConversationControls />
      <p className="muted">Chat and Research share the selected conversation. Citations appear on the Research tab.</p>
      {view.streamNotice && <p className="notice error">{view.streamNotice}</p>}
      <ChatThread
        placeholder="Ask me anything about your documents…"
        messages={view.messages}
        streaming={view.streaming}
        progress={view.progress}
        retryable={view.retryable}
        onRetry={() => view.conversationId && view.retryable && void retryRun(queryClient, view.conversationId, view.retryable.id)}
      />
      <Composer placeholder="Type a message…" replyTo={view.replyTo} />
    </section>
  )
}
