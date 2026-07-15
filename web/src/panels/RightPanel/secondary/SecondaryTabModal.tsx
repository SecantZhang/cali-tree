import { ResizeHandle } from '../../../components/ResizeHandle'
import { useActiveGraphStore } from '../../../store/activeTab'
import { usePrefsStore } from '../../../store/prefsStore'
import { ClAdversarialSecondaryTab } from './ClAdversarialSecondaryTab'
import { ClRuleEvalSecondaryTab } from './ClRuleEvalSecondaryTab'
import { ClRuleTreeSecondaryTab } from './ClRuleTreeSecondaryTab'
import { DatasetSecondaryTab } from './DatasetSecondaryTab'
import { EvalSecondaryTab } from './EvalSecondaryTab'
import { JudgeSecondaryTab } from './JudgeSecondaryTab'
import { LMEngineSecondaryTab } from './LMEngineSecondaryTab'
import { SourceSecondaryTab } from './SourceSecondaryTab'

const SOURCE_TYPES = new Set(['peanut_source'])
const JUDGE_TYPES = new Set(['judge'])
const EVAL_TYPES = new Set(['eval'])

export function SecondaryTabModal() {
  const nodeId = useActiveGraphStore((s) => s.secondaryTabNodeId)
  const node = useActiveGraphStore((s) => s.nodes.find((n) => n.id === s.secondaryTabNodeId))
  const close = useActiveGraphStore((s) => s.closeSecondaryTab)
  const modalWidth = usePrefsStore((s) => s.modalWidth)
  const modalHeight = usePrefsStore((s) => s.modalHeight)
  const setModalWidth = usePrefsStore((s) => s.setModalWidth)
  const setModalHeight = usePrefsStore((s) => s.setModalHeight)

  if (!nodeId || !node) return null

  const type = node.type ?? ''

  // Ending a resize drag (below) can leave the cursor past the panel's new edge, over this
  // backdrop — the modal centers itself, so widening it moves both edges toward the cursor,
  // not just the one being dragged. The resulting click must not close the modal; guarded
  // by the same 'is-resizing' class ResizeHandle already toggles during any drag (see its
  // own comment on why the class removal is deferred a tick past the drag's mouseup).
  const handleOverlayClick = () => {
    if (!document.body.classList.contains('is-resizing')) close()
  }

  return (
    <div className="modal-overlay" onClick={handleOverlayClick}>
      <div
        className="modal-panel"
        style={{ width: modalWidth, height: modalHeight, maxWidth: '95vw', maxHeight: '92vh' }}
        onClick={(e) => e.stopPropagation()}
      >
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
          {EVAL_TYPES.has(type) && <EvalSecondaryTab node={node} />}
          {type === 'cl_rule_eval' && <ClRuleEvalSecondaryTab node={node} />}
          {type === 'preprocessing' && (
            <p className="empty-hint">
              Pass-through stub — no artifacts are extracted yet, so there's nothing to
              inspect here.
            </p>
          )}
          {type === 'lm_engine' && <LMEngineSecondaryTab node={node} />}
          {type === 'judge_prompt' && (
            <p className="empty-hint">
              A metric preset (M1–M6) or a custom free-text judge. Edit its fields in the
              node/Inspector; a preset's exact prompt is resolved per item and shown in the
              downstream Judge node's secondary tab (per-item prompt + parsed output).
            </p>
          )}
          {type === 'cl_adversarial' && <ClAdversarialSecondaryTab node={node} />}
          {type === 'cl_rule_tree' && <ClRuleTreeSecondaryTab node={node} />}
        </div>
        <ResizeHandle
          orientation="vertical"
          onResize={(delta) => setModalWidth(usePrefsStore.getState().modalWidth + delta)}
        />
        <ResizeHandle
          orientation="horizontal"
          onResize={(delta) => setModalHeight(usePrefsStore.getState().modalHeight + delta)}
        />
      </div>
    </div>
  )
}
