import { useMemo, useState } from 'react'
import { useActiveRunStore } from '../../../store/activeTab'
import type { VeNode } from '../../../store/graphStore'
import { JudgeSamplePreview } from './JudgeSamplePreview'

export function ImagenHubSourceSecondaryTab({ node }: { node: VeNode }) {
  const lastResult = useActiveRunStore((s) => s.lastNodeResults[node.id])
  const outputs = lastResult?.outputs as Record<string, unknown> | undefined
  const samples = (outputs?.raw_dataset ?? {}) as Record<string, Record<string, unknown>>
  const labels = (outputs?.raw_labels ?? {}) as Record<string, Record<string, unknown>>
  const ids = useMemo(() => Object.keys(samples).sort(), [samples])
  const [selected, setSelected] = useState<string | null>(null)
  const selectedId = selected && samples[selected] ? selected : ids[0]
  const meta = lastResult?.meta as Record<string, unknown> | undefined

  return (
    <div>
      <div className="secondary-summary">
        <div><strong>Loader:</strong> ImagenHub text-guided image editing</div>
        <div><strong>Repeat:</strong> {String(meta?.repeat ?? node.data.params.repeat ?? 1)}</div>
        <div><strong>Items:</strong> {String(meta?.n_items ?? ids.length)}</div>
        {ids.length === 0 && (
          <p className="meta-warning">
            No materialized data. Run <code>./run/setup_imagenhub.sh</code>, then execute this node.
          </p>
        )}
      </div>
      {ids.length > 0 && (
        <div className="secondary-split">
          <ul className="dataset-item-list secondary-item-list">
            {ids.map((id) => (
              <li key={id} className={id === selectedId ? 'active' : ''} onClick={() => setSelected(id)}>
                {id} · {String(samples[id].split ?? '')}
              </li>
            ))}
          </ul>
          <div className="item-preview">
            {selectedId && (
              <JudgeSamplePreview item={samples[selectedId]} label={labels[selectedId]} />
            )}
          </div>
        </div>
      )}
    </div>
  )
}
