import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { getItem, listItems } from '../../../api/datasets'
import { mediaUrl } from '../../../api/media'
import { ProgressBar } from '../../../components/ProgressBar'
import { useActiveRunStore } from '../../../store/activeTab'
import type { VeNode } from '../../../store/graphStore'

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
              <ItemPreview item={itemQuery.data as Record<string, unknown>} />
            ) : (
              <p className="empty-hint">Select an item to preview it.</p>
            )}
          </div>
        </div>
      )}
    </div>
  )
}

function ItemPreview({ item }: { item: Record<string, unknown> }) {
  // peanut_eval (JudgeSample) shape.
  const input = (item.input as Record<string, unknown>) ?? {}
  const output = (item.output as Record<string, unknown>) ?? {}
  return (
    <div>
      <h4>{String(item.item_id ?? '')}</h4>
      <div className="item-field"><strong>use_case:</strong> {String(item.use_case ?? '')}</div>
      <div className="item-field"><strong>prompt:</strong> {String(input.user_prompt ?? '')}</div>
      {typeof output.output_video_path === 'string' && output.output_video_path && (
        <div className="item-field">
          <strong>video:</strong>
          <video
            controls preload="metadata" className="item-video"
            src={mediaUrl(output.output_video_path)}
          />
          <div><span className="mono-path">{output.output_video_path}</span></div>
        </div>
      )}
      {typeof input.b_roll_captions_excerpt === 'string' && input.b_roll_captions_excerpt && (
        <details>
          <summary>B-roll captions</summary>
          <pre className="json-preview">{input.b_roll_captions_excerpt}</pre>
        </details>
      )}
      {typeof input.a_roll_transcript_text === 'string' && input.a_roll_transcript_text && (
        <details>
          <summary>A-roll transcript</summary>
          <pre className="json-preview">{input.a_roll_transcript_text}</pre>
        </details>
      )}
      {output.assembly_json != null && (
        <details>
          <summary>Assembly JSON</summary>
          <pre className="json-preview">{JSON.stringify(output.assembly_json, null, 2)}</pre>
        </details>
      )}
      <details>
        <summary>Raw JSON</summary>
        <pre className="json-preview">{JSON.stringify(item, null, 2)}</pre>
      </details>
    </div>
  )
}
