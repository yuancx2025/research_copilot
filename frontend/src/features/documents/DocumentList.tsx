import { useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { clearDocuments, listDocuments } from '../../api/endpoints'

export function DocumentList() {
  const queryClient = useQueryClient()
  const documents = useQuery({ queryKey: ['documents'], queryFn: listDocuments })
  const [clearing, setClearing] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const clearAll = async () => {
    if (!window.confirm('Remove every document from the knowledge base?')) return
    setClearing(true)
    setError(null)
    try {
      queryClient.setQueryData(['documents'], await clearDocuments())
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not clear documents.')
    } finally {
      setClearing(false)
    }
  }

  const names = documents.data?.documents ?? []
  return (
    <div className="document-list">
      {documents.isLoading ? (
        <p className="muted">Loading documents…</p>
      ) : names.length ? (
        <ul>
          {names.map((name) => (
            <li key={name}>{name}</li>
          ))}
        </ul>
      ) : (
        <p className="muted">No documents in the knowledge base yet.</p>
      )}
      {(error || documents.isError) && (
        <p className="notice error">{error ?? 'Could not load documents.'}</p>
      )}
      <div className="row">
        <button onClick={() => documents.refetch()} disabled={documents.isFetching}>
          Refresh
        </button>
        <button className="danger" onClick={clearAll} disabled={clearing || !names.length}>
          Clear all
        </button>
      </div>
    </div>
  )
}
