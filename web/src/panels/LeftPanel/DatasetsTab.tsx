import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { listItems, listLoaders } from '../../api/datasets'

export function DatasetsTab() {
  const [loader, setLoader] = useState<string | null>(null)
  const loadersQuery = useQuery({ queryKey: ['loaders'], queryFn: listLoaders })
  const itemsQuery = useQuery({
    queryKey: ['datasetItems', loader],
    queryFn: () => listItems(loader as string),
    enabled: !!loader,
  })

  if (loadersQuery.isLoading) return <p className="empty-hint">Loading loaders…</p>
  if (loadersQuery.isError || !loadersQuery.data) {
    return <p className="empty-hint">Could not reach the backend. Is vejudge-interface running?</p>
  }

  return (
    <div>
      <select value={loader ?? ''} onChange={(e) => setLoader(e.target.value || null)}>
        <option value="">Select a loader…</option>
        {loadersQuery.data.map((l) => (
          <option key={l} value={l}>
            {l}
          </option>
        ))}
      </select>
      {itemsQuery.isLoading && <p className="empty-hint">Loading items…</p>}
      {itemsQuery.data && (
        <>
          {itemsQuery.data.items.length === 0 && (
            <p className="empty-hint">No items found (check data/rendered-output paths).</p>
          )}
          <ul className="dataset-item-list">
            {itemsQuery.data.items.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </>
      )}
    </div>
  )
}
