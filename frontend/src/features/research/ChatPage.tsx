import { ChatThread } from './ChatThread'
import { Composer } from './Composer'

export function ChatPage() {
  return (
    <section className="panel conversation chat-page">
      <p className="muted">Chat and Research share one conversation. Citations appear on the Research tab.</p>
      <ChatThread placeholder="Ask me anything about your documents…" />
      <Composer placeholder="Type a message…" />
    </section>
  )
}
