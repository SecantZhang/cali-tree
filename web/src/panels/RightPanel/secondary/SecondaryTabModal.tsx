import { useActiveGraphStore } from '../../../store/activeTab'
import { DatasetSecondaryTab } from './DatasetSecondaryTab'
import { EvalSecondaryTab } from './EvalSecondaryTab'
import { JudgeSecondaryTab } from './JudgeSecondaryTab'
import { SourceSecondaryTab } from './SourceSecondaryTab'

const SOURCE_TYPES = new Set(['peanut_source'])
const JUDGE_TYPES = new Set(['judge_text', 'judge_video'])

export function SecondaryTabModal() {
  const nodeId = useActiveGraphStore((s) => s.secondaryTabNodeId)
  const node = useActiveGraphStore((s) => s.nodes.find((n) => n.id === s.secondaryTabNodeId))
  const close = useActiveGraphStore((s) => s.closeSecondaryTab)

  if (!nodeId || !node) return null

  const type = node.type ?? ''

  return (
    <div className="modal-overlay" onClick={close}>
      <div className="modal-panel" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <strong>
            {node.type} — {node.id}
          </strong>
          <button onClick={close}>Close</button>
        </div>
        <div className="modal-body">
          {SOURCE_TYPES.has(type) && <SourceSecondaryTab node={node} />}
          {type === 'dataset' && <DatasetSecondaryTab node={node} />}
          {JUDGE_TYPES.has(type) && <JudgeSecondaryTab node={node} />}
          {type === 'eval' && <EvalSecondaryTab node={node} />}
          {type === 'preprocessing' && (
            <p className="empty-hint">
              Pass-through stub — no artifacts are extracted yet, so there's nothing to
              inspect here.
            </p>
          )}
          {type === 'lm_engine' && (
            <p className="empty-hint">
              Configuration only — the params panel already shows everything this node
              carries. A live tail of this engine's llm-histories.log slice (per
              interface.md's spec) isn't implemented yet.
            </p>
          )}
        </div>
      </div>
    </div>
  )
}
