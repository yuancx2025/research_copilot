import styles from './documents.module.css'
import { useRef } from 'react'
import { useQuery } from '@tanstack/react-query'
import { documentOptions, useClearDocuments } from './queries'
export function DocumentList() {
  const documents = useQuery(documentOptions())
  const clearing = useClearDocuments()
  const lock = useRef(false)
  const clearAll = async () => {
    if (lock.current || !window.confirm('Remove every document from the knowledge base?')) return
    lock.current = true
    try { await clearing.mutateAsync() } catch { /* Render mutation error. */ }
    finally { lock.current = false }
  }
  const names = documents.data?.documents ?? []
  return <div className={styles["document-list"]}>
    {documents.isPending ? <p className="muted">Loading documents…</p> : documents.isError ? null : names.length
      ? <ul>{names.map((name) => <li key={name}>{name}</li>)}</ul>
      : <p className="muted">No documents in the knowledge base yet.</p>}
    {(clearing.error || documents.error) && <p className="notice error" role="alert">{clearing.error?.message ?? 'Could not load documents.'}</p>}
    <div className="row">
      <button onClick={() => void documents.refetch()} disabled={documents.isFetching}>Refresh</button>
      <button className="danger" onClick={clearAll} disabled={clearing.isPending || !names.length}>Clear all</button>
    </div>
  </div>
}
