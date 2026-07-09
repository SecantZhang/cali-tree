import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { getItem, listItems } from '../../../api/datasets'
import { ProgressBar } from '../../../components/ProgressBar'
import { useActiveRunStore } from '../../../store/activeTab'
import type { VeNode } from '../../../store/graphStore'
import { JudgeSamplePreview } from './JudgeSamplePreview'

export function SourceSecondaryTab({ node }: { node: VeNode }) {
  const loader = 'peanut_eval'
  const model = String(node.data.params.model ?? 'peanut')
  const projects = (node.data.params.projects as string[] | null) ?? null
  const [selectedItem, setSelectedItem] = useState<string | null>(null)

  const lastResult = useActiveRunStore((s) => s.lastNodeResults[node.id])
  const nodeProgress = useActiveRunStore((s) => s.nodeProgress[node.id])

  const itemsQuery = useQuery({
    queryKey: ['secondarySourceItems', loader, model],
    queryFn: () => listItems(loader, { model }),
  })
  const itemQuery = useQuery({
    queryKey: ['secondarySourceItem', loader, selectedItem, model],
    queryFn: () => getItem(loader, selectedItem as string, model),
    enabled: !!selectedItem,
  })

  const lastOutputs = lastResult?.outputs as Record<string, unknown> | undefined
  const lastItems = lastOutputs?.raw_dataset as Record<string, { use_case?: string }> | undefined
  const useCaseBreakdown = lastItems
    ? Object.values(lastItems).reduce<Record<string, number>>((acc, item) => {
      const uc = item.use_case ?? 'unknown'
      acc[uc] = (acc[uc] ?? 0) + 1
      return acc
    }, {})
    : null
  const meta = lastResult?.meta as
    | { n_items?: number; skipped_items?: string[]; warning?: string }
    | undefined

  return (
    <div>
      <div className="secondary-summary">
        <div><strong>Loader:</strong> {loader}</div>
        <div><strong>Model:</strong> {model}</div>
        <div><strong>Projects:</strong> {projects?.length ? projects.join(', ') : 'all'}</div>
        {meta && (
          <div>
            <strong>Last run:</strong> {meta.n_items ?? 0} item(s)
            {(meta.skipped_items?.length ?? 0) > 0 && ` — ${meta.skipped_items!.length} skipped`}
          </div>
        )}
        {useCaseBreakdown && (
          <div>
            <strong>Use cases:</strong>{' '}
            {Object.entries(useCaseBreakdown).map(([uc, n]) => `${uc} (${n})`).join(', ')}
          </div>
        )}
        {meta?.warning && <p className="meta-warning">{meta.warning}</p>}
        {node.data.status === 'running' && (
          <ProgressBar progress={nodeProgress ?? { completed: 0, total: null }} label="Loading…" />
        )}
      </div>

      {itemsQuery.isLoading && <p className="empty-hint">Loading items…</p>}
      {(itemsQuery.isError || !itemsQuery.data) && !itemsQuery.isLoading && (
        <p className="empty-hint">Could not load items for loader '{loader}'.</p>
      )}
      {itemsQuery.data && (
        <div className="secondary-split">
          <ul className="dataset-item-list secondary-item-list">
            {itemsQuery.data.items.map((item) => (
              <li
                key={item}
                className={item === selectedItem ? 'active' : ''}
                onClick={() => setSelectedItem(item)}
              >
                {item}
              </li>
            ))}
            {itemsQuery.data.items.length === 0 && <li className="empty-hint">No items found.</li>}
          </ul>
          <div className="item-preview">
            {itemQuery.data ? (
              <JudgeSamplePreview item={itemQuery.data as Record<string, unknown>} />
            ) : (
              <p className="empty-hint">Select an item to preview it.</p>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
