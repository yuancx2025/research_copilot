import styles from './documents.module.css'
import { useRef, useState, type DragEvent } from 'react'
import { useUploadDocuments } from './useUploadDocuments'

const ACCEPTED = /\.(pdf|md)$/i

interface Status {
  kind: 'ok' | 'error'
  text: string
}

export function UploadDropzone({ compact = false }: { compact?: boolean }) {
  const action = useUploadDocuments()
  const uploading = action.isPending
  const progress = action.progress
  const lock = useRef(false)
  const inputRef = useRef<HTMLInputElement>(null)
  const [files, setFiles] = useState<File[]>([])
  const [dragging, setDragging] = useState(false)
  const [status, setStatus] = useState<Status | null>(null)

  const choose = (list: FileList | null) => {
    if (uploading) return
    const all = Array.from(list ?? [])
    const accepted = all.filter((file) => ACCEPTED.test(file.name))
    setFiles(accepted)
    setStatus(accepted.length < all.length ? { kind: 'error', text: 'Only PDF and Markdown files are accepted.' } : null)
  }

  const onDrop = (event: DragEvent<HTMLLabelElement>) => {
    event.preventDefault()
    setDragging(false)
    choose(event.dataTransfer.files)
  }

  const upload = async () => {
    if (lock.current) return
    lock.current = true
    setStatus(null)
    try {
      const event = await action.mutateAsync(files)
      const skipped = event.skipped ? ` · Skipped ${event.skipped} duplicate or unsupported file(s)` : ''
      setStatus({ kind: 'ok', text: `Indexed ${event.added} document(s)${skipped}` })
      setFiles([])
    } catch (error) {
      setStatus({ kind: 'error', text: error instanceof Error ? error.message : 'Upload failed.' })
    } finally {
      lock.current = false
      if (inputRef.current) inputRef.current.value = ''
    }
  }

  return (
    <div className={`${styles.uploader} ${compact ? styles.compact : ''}`}>
      <label
        className={`${styles.dropzone} ${dragging ? styles.dragging : ''}`}
        onDragOver={(event) => {
          event.preventDefault()
          setDragging(true)
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={onDrop}
      >
        <input
          ref={inputRef}
          type="file"
          multiple
          accept=".pdf,.md"
          onChange={(event) => choose(event.target.files)}
          disabled={uploading}
        />
        <span>
          {files.length
            ? files.map((file) => file.name).join(', ')
            : 'Drop PDF or Markdown files here, or click to choose'}
        </span>
      </label>
      <button className="primary" onClick={upload} disabled={!files.length || uploading}>
        {uploading ? 'Indexing…' : compact ? 'Index documents' : 'Add documents'}
      </button>
      {progress && (
        <div className={styles["progress"]} role="progressbar" aria-valuenow={Math.round(progress.fraction * 100)}>
          <div className={styles["progress-bar"]} style={{ width: `${Math.max(progress.fraction, 0.05) * 100}%` }} />
          <span>{progress.message}</span>
        </div>
      )}
      {status && <p className={`notice ${status.kind}`}>{status.text}</p>}
    </div>
  )
}
