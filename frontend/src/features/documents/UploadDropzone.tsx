import { useRef, useState, type DragEvent } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { uploadDocuments } from '../../api/endpoints'

const ACCEPTED = /\.(pdf|md)$/i

interface Status {
  kind: 'ok' | 'error'
  text: string
}

export function UploadDropzone({ compact = false }: { compact?: boolean }) {
  const queryClient = useQueryClient()
  const inputRef = useRef<HTMLInputElement>(null)
  const [files, setFiles] = useState<File[]>([])
  const [dragging, setDragging] = useState(false)
  const [uploading, setUploading] = useState(false)
  const [progress, setProgress] = useState<{ fraction: number; message: string } | null>(null)
  const [status, setStatus] = useState<Status | null>(null)

  const choose = (list: FileList | null) => {
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
    setUploading(true)
    setStatus(null)
    setProgress({ fraction: 0, message: 'Uploading' })
    try {
      await uploadDocuments(files, (event) => {
        if (event.type === 'progress') setProgress(event)
        else if (event.type === 'error') setStatus({ kind: 'error', text: event.message })
        else {
          const skipped = event.skipped ? ` · Skipped ${event.skipped} duplicate or unsupported file(s)` : ''
          setStatus({ kind: 'ok', text: `Indexed ${event.added} document(s)${skipped}` })
          queryClient.setQueryData(['documents'], { documents: event.documents })
          setFiles([])
        }
      })
    } catch (error) {
      setStatus({ kind: 'error', text: error instanceof Error ? error.message : 'Upload failed.' })
    } finally {
      setUploading(false)
      setProgress(null)
      if (inputRef.current) inputRef.current.value = ''
    }
  }

  return (
    <div className={compact ? 'uploader compact' : 'uploader'}>
      <label
        className={dragging ? 'dropzone dragging' : 'dropzone'}
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
        <div className="progress" role="progressbar" aria-valuenow={Math.round(progress.fraction * 100)}>
          <div className="progress-bar" style={{ width: `${Math.max(progress.fraction, 0.05) * 100}%` }} />
          <span>{progress.message}</span>
        </div>
      )}
      {status && <p className={`notice ${status.kind}`}>{status.text}</p>}
    </div>
  )
}
