import styles from './research.module.css'
import { useParams } from 'react-router-dom'
import type { AppConfig } from '../../api/types'
import { UploadDropzone } from '../documents'
import { NotionConnectionBar } from '../integrations/notion'
import { StudyPlanPanel } from '../study-plan'
import { ArtifactsPanel } from './components/ArtifactsPanel'
import { ChatThread } from './components/ChatThread'
import { Composer } from './components/Composer'
import { ConversationControls } from './components/ConversationControls'
import { ConversationStatus } from './components/ConversationStatus'
import { useConversationView } from './hooks/useConversation'
import { useResearchActions } from './hooks/useResearchActions'

export function ResearchPage({ config }: { config: AppConfig }) {
  const { conversationId } = useParams()
  const view = useConversationView(conversationId)
  const action = useResearchActions(conversationId ?? '')
  const oauth = config.notion_backend === 'mcp'
  return (
    <div className={styles["research-layout"]}>
      <section className={["panel", styles["conversation"]].join(' ')}>
        <h2>Research assistant</h2>
        <ConversationControls />
        <p className="muted">Explore papers, videos, repositories, web articles{oauth ? ', and your connected Notion notes' : ''}.</p>
        {oauth && <NotionConnectionBar />}
        <ConversationStatus view={view} />
        {!view.loading && !view.error && <>
          <ChatThread placeholder="Ask a research question, for example “What are the latest transformer architectures?”"
            messages={view.messages} streaming={view.streaming} progress={view.progress} retryable={view.retryable}
            retryPending={action.pending}
            onRetry={() => { if (view.retryable) void action.mutateAsync({ text: '', retryOf: view.retryable.id }).catch(() => {}) }} />
          {action.error && <p className="notice error" role="alert">{action.error.message}</p>}
          <Composer key={conversationId ?? 'new'} conversationId={conversationId} runActive={view.streaming}
            placeholder="Type your research question here…" replyTo={view.replyTo} />
        </>}
      </section>
      <aside className={styles["artifacts"]}>
        <ArtifactsPanel result={view.result} />
        {config.notion_backend !== 'disabled' && <StudyPlanPanel key={conversationId} config={config} run={view.resultRun} draft={view.draft}
          busy={view.streaming || view.loading || Boolean(view.error)} />}
        <details className="panel"><summary>Upload documents for research</summary><UploadDropzone compact /></details>
      </aside>
    </div>
  )
}
