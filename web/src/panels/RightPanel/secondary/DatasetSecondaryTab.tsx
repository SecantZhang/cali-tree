import { useState } from 'react'
import { ProgressBar } from '../../../components/ProgressBar'
import {
  HUMAN_LABEL_SCHEMA,
  JUDGE_SAMPLE_SCHEMA,
  type SchemaField,
} from '../../../nodes/judgeSampleSchema'
import { useActiveRunStore } from '../../../store/activeTab'
import type { VeNode } from '../../../store/graphStore'
import { JudgeSamplePreview } from './JudgeSamplePreview'

export function DatasetSecondaryTab({ node }: { node: VeNode }) {
  const samplingMode = String(node.data.params.sampling_mode ?? 'full')
  const samplingRatio = Number(node.data.params.sampling_ratio ?? 1)
  const useCaseFilter = (node.data.params.use_case_filter as string[] | null) ?? null
  const itemIdPattern = (node.data.params.item_id_pattern as string | null) ?? null

  const lastResult = useActiveRunStore((s) => s.lastNodeResults[node.id])
  const nodeProgress = useActiveRunStore((s) => s.nodeProgress[node.id])
  const meta = lastResult?.meta as
    | { n_items?: number; n_raw_items?: number; n_labels?: number; warning?: string }
    | undefined

  // The node's own sampled output — the actual per-item data + joined human labels, keyed
  // by item id. Present once this node has completed a run (fetched into lastNodeResults via
  // the run-status GET; see useRunSocket). `labels` omits items with no annotation.
  const outputs = lastResult?.outputs as Record<string, unknown> | undefined
  const samples = outputs?.samples as Record<string, Record<string, unknown>> | undefined
  const labels = outputs?.labels as Record<string, Record<string, unknown>> | undefined
  const itemIds = samples ? Object.keys(samples) : []

  const [selectedItem, setSelectedItem] = useState<string | null>(null)
  const selected = selectedItem && samples ? samples[selectedItem] : null

  return (
    <div>
      <div className="secondary-summary">
        <div>
          <strong>Sampling:</strong> {samplingMode}
          {samplingMode !== 'full' && ` (${Math.round(samplingRatio * 100)}%)`}
        </div>
        <div>
          <strong>Use case filter:</strong> {useCaseFilter?.length ? useCaseFilter.join(', ') : 'none'}
        </div>
        <div><strong>Item id pattern:</strong> {itemIdPattern || 'none'}</div>
        {meta && (
          <div>
            <strong>Last run:</strong> {meta.n_items ?? 0} / {meta.n_raw_items ?? 0} item(s) selected,{' '}
            {meta.n_labels ?? 0} with matching human label(s)
          </div>
        )}
        {meta?.warning && <p className="meta-warning">{meta.warning}</p>}
        {node.data.status === 'running' && (
          <ProgressBar progress={nodeProgress ?? { completed: 0, total: null }} label="Sampling…" />
        )}
      </div>

      {/* Static field reference — available regardless of whether a run has happened, since
          it describes the data shape, not any particular run's values. Collapsed by default. */}
      <details className="schema-details">
        <summary>Schema — what each sampled item and its label contain</summary>
        <h5 className="schema-heading">Sampled item (JudgeSample)</h5>
        <SchemaTable fields={JUDGE_SAMPLE_SCHEMA} />
        <h5 className="schema-heading">Human label (joined by item_id)</h5>
        <SchemaTable fields={HUMAN_LABEL_SCHEMA} />
      </details>

      {!samples && (
        <p className="empty-hint">Run this node to browse the resulting sampled items here.</p>
      )}
      {samples && (
        <div className="secondary-split">
          <ul className="dataset-item-list secondary-item-list">
            {itemIds.map((id) => (
              <li
                key={id}
                className={id === selectedItem ? 'active' : ''}
                onClick={() => setSelectedItem(id)}
              >
                {id}
                {labels?.[id] && <span className="item-has-label" title="Has a human label">●</span>}
              </li>
            ))}
            {itemIds.length === 0 && <li className="empty-hint">No items sampled.</li>}
          </ul>
          <div className="item-preview">
            {selected ? (
              <JudgeSamplePreview item={selected} label={selectedItem ? labels?.[selectedItem] : undefined} />
            ) : (
              <p className="empty-hint">Select an item to preview it.</p>
            )}
          </div>
        </div>
      )}
    </div>
  )
}

function SchemaTable({ fields }: { fields: SchemaField[] }) {
  return (
    <table className="schema-table">
      <tbody>
        {fields.map((f) => (
          <tr key={f.field}>
            <td className="schema-field">{f.field}</td>
            <td className="schema-type">{f.type}</td>
            <td className="schema-desc">{f.description}</td>
          </tr>
        ))}
      </tbody>
    </table>
  )
}
