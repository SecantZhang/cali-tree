import { useGraphStore } from '../../../store/graphStore'
import { DatasetSecondaryTab } from './DatasetSecondaryTab'
import { EvalSecondaryTab } from './EvalSecondaryTab'
import { JudgeSecondaryTab } from './JudgeSecondaryTab'

export function SecondaryTabModal() {
  const nodeId = useGraphStore((s) => s.secondaryTabNodeId)
  const node = useGraphStore((s) => s.nodes.find((n) => n.id === s.secondaryTabNodeId))
  const close = useGraphStore((s) => s.closeSecondaryTab)

  if (!nodeId || !node) return null

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
          {node.type === 'dataset' && <DatasetSecondaryTab node={node} />}
          {node.type === 'judge' && <JudgeSecondaryTab node={node} />}
          {node.type === 'eval' && <EvalSecondaryTab node={node} />}
        </div>
      </div>
    </div>
  )
}
