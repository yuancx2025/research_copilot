import type { AppConfig } from '../../api/types'
import { UploadDropzone } from '../documents/UploadDropzone'
import { NotionConnectionBar } from '../notion/NotionConnectionBar'
import { StudyPlanPanel } from '../notion/StudyPlanPanel'
import { ArtifactsPanel } from './ArtifactsPanel'
import { ChatThread } from './ChatThread'
import { Composer } from './Composer'

export function ResearchPage({ config }: { config: AppConfig }) {
  const oauth = config.notion_backend === 'mcp'
  return (
    <div className="research-layout">
      <section className="panel conversation">
        <h2>Research assistant</h2>
        <p className="muted">
          Explore papers, videos, repositories, web articles{oauth ? ', and your connected Notion notes' : ''}.
        </p>
        {oauth && <NotionConnectionBar />}
        <ChatThread placeholder="Ask a research question, for example “What are the latest transformer architectures?”" />
        <Composer placeholder="Type your research question here…" />
      </section>
      <aside className="artifacts">
        <ArtifactsPanel />
        {config.notion_backend !== 'disabled' && <StudyPlanPanel config={config} />}
        <details className="panel">
          <summary>Upload documents for research</summary>
          <UploadDropzone compact />
        </details>
      </aside>
    </div>
  )
}
