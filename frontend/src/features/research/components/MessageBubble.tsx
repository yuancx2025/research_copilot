import styles from '../research.module.css'
import { Markdown } from '../../../shared/components/Markdown'
import type { ConversationMessage } from '../../../api/types'

export function MessageBubble({ message }: { message: ConversationMessage }) {
  return (
    <div className={`${styles.message} ${styles[message.role]}`} data-role={message.role}>
      {message.role === 'assistant' ? <Markdown>{message.content}</Markdown> : <p>{message.content}</p>}
      {message.clarification && <span className={styles["badge"]}>Reply to clarify</span>}
    </div>
  )
}
