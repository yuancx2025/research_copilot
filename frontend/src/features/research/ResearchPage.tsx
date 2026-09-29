import { useQueryClient } from '@tanstack/react-query'
import type { AppConfig } from '../../api/types'
import { retryRun } from '../../store/researchStore'
import { UploadDropzone } from '../documents/UploadDropzone'
import { NotionConnectionBar } from '../notion/NotionConnectionBar'
import { StudyPlanPanel } from '../notion/StudyPlanPanel'
import { ArtifactsPanel } from './ArtifactsPanel'
import { ChatThread } from './ChatThread'
import { Composer } from './Composer'
import { ConversationControls } from './ConversationControls'
import { useConversationView } from './useConversation'

export function ResearchPage({ config }: { config: AppConfig }) {
  const queryClient = useQueryClient()
  const view = useConversationView()
  const oauth = config.notion_backend === 'mcp'
  return (
    <div className="research-layout">
      <section className="panel conversation">
        <h2>Research assistant</h2>
        <ConversationControls />
        <p className="muted">
          Explore papers, videos, repositories, web articles{oauth ? ', and your connected Notion notes' : ''}.
        </p>
        {oauth && <NotionConnectionBar />}
        {view.streamNotice && <p className="notice error">{view.streamNotice}</p>}
        <ChatThread
          placeholder="Ask a research question, for example “What are the latest transformer architectures?”"
          messages={view.messages}
          streaming={view.streaming}
          progress={view.progress}
          retryable={view.retryable}
          onRetry={() => view.conversationId && view.retryable && void retryRun(queryClient, view.conversationId, view.retryable.id)}
        />
        <Composer placeholder="Type your research question here…" replyTo={view.replyTo} />
      </section>
      <aside className="artifacts">
        <ArtifactsPanel result={view.result} />
        {config.notion_backend !== 'disabled' && (
          <StudyPlanPanel config={config} run={view.resultRun} draft={view.draft} />
        )}
        <details className="panel">
          <summary>Upload documents for research</summary>
          <UploadDropzone compact />
        </details>
      </aside>
    </div>
  )
}
