import styles from './notion.module.css'
import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { destinationOptions, notionStatusOptions } from './queries'
export function DestinationPicker({ onPick }: { onPick: (ref: string) => void }) {
  const [query, setQuery] = useState('')
  const [submitted, setSubmitted] = useState<string | null>(null)
  const status = useQuery(notionStatusOptions(true))
  const generation = status.data?.generation ?? null
  const pages = useQuery(destinationOptions(generation, submitted))
  const search = () => {
    const text = query.trim()
    if (submitted === text) void pages.refetch()
    else setSubmitted(text)
  }
  return <div className={styles["destination-picker"]}>
    <div className="row">
      <input aria-label="Search destination pages" placeholder="Search your Notion pages" value={query}
        onChange={(event) => setQuery(event.target.value)}
        onKeyDown={(event) => { if (event.key === 'Enter') { event.preventDefault(); search() } }} />
      <button onClick={search} disabled={pages.isFetching}>{pages.isFetching ? 'Searching…' : 'Search'}</button>
    </div>
    {pages.data && <select key={`${generation}:${submitted}`} aria-label="Matching pages" defaultValue="" onChange={(event) => onPick(event.target.value)}>
      <option value="" disabled>{pages.data.length ? `${pages.data.length} matching page(s)` : 'No matching pages'}</option>
      {pages.data.map((page) => <option key={page.ref} value={page.ref}>{page.title}</option>)}
    </select>}
    {pages.error && <p className="notice error" role="alert">{pages.error.message}</p>}
  </div>
}
