import { useState } from 'react'
import { searchNotionPages } from '../../api/endpoints'
import type { NotionPage } from '../../api/types'

export function DestinationPicker({ onPick }: { onPick: (ref: string) => void }) {
  const [query, setQuery] = useState('')
  const [pages, setPages] = useState<NotionPage[] | null>(null)
  const [searching, setSearching] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const search = async () => {
    setSearching(true)
    setError(null)
    try {
      setPages(await searchNotionPages(query))
    } catch (err) {
      setPages(null)
      setError(err instanceof Error ? err.message : 'Could not search destinations.')
    } finally {
      setSearching(false)
    }
  }

  return (
    <div className="destination-picker">
      <div className="row">
        <input
          aria-label="Search destination pages"
          placeholder="Search your Notion pages"
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === 'Enter') {
              event.preventDefault()
              void search()
            }
          }}
        />
        <button onClick={search} disabled={searching}>
          {searching ? 'Searching…' : 'Search'}
        </button>
      </div>
      {pages && (
        <select aria-label="Matching pages" defaultValue="" onChange={(event) => onPick(event.target.value)}>
          <option value="" disabled>
            {pages.length ? `${pages.length} matching page(s)` : 'No matching pages'}
          </option>
          {pages.map((page) => (
            <option key={page.ref} value={page.ref}>
              {page.title}
            </option>
          ))}
        </select>
      )}
      {error && <p className="notice error">{error}</p>}
    </div>
  )
}
