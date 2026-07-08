import { ProgressBar } from '../../../components/ProgressBar'
import { useActiveRunStore } from '../../../store/activeTab'
import type { VeNode } from '../../../store/graphStore'

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
      {!meta && (
        <p className="empty-hint">Run this node to see the resulting selection count here.</p>
      )}
    </div>
  )
}
