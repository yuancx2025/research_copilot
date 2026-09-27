import { DocumentList } from './DocumentList'
import { UploadDropzone } from './UploadDropzone'

export function DocumentsPage() {
  return (
    <div className="documents-page">
      <section className="panel">
        <h2>Add documents</h2>
        <p className="muted">Upload PDF or Markdown files. Duplicates are skipped automatically.</p>
        <UploadDropzone />
      </section>
      <section className="panel">
        <h2>Knowledge base</h2>
        <DocumentList />
      </section>
    </div>
  )
}
