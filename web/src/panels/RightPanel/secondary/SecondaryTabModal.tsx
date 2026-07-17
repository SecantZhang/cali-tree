import { useState } from 'react'
import { ResizeHandle } from '../../../components/ResizeHandle'
import { useActiveGraphStore } from '../../../store/activeTab'
import type { VeNode } from '../../../store/graphStore'
import { usePrefsStore } from '../../../store/prefsStore'
import { ClAdversarialSecondaryTab } from './ClAdversarialSecondaryTab'
import { ClRuleEvalSecondaryTab } from './ClRuleEvalSecondaryTab'
import { ClRuleTreeSecondaryTab } from './ClRuleTreeSecondaryTab'
import { DatasetSecondaryTab } from './DatasetSecondaryTab'
import { EvalSecondaryTab } from './EvalSecondaryTab'
import { JudgeSecondaryTab } from './JudgeSecondaryTab'
import { LMEngineSecondaryTab } from './LMEngineSecondaryTab'
import { NodeInputsTab } from './NodeInputsTab'
import { NodeOutputsTab } from './NodeOutputsTab'
import { NodeTimingTab } from './NodeTimingTab'
import { SourceSecondaryTab } from './SourceSecondaryTab'

const JUDGE_TYPES = new Set(['judge'])
const EVAL_TYPES = new Set(['eval'])

// The node-type-specific ("Details") view. Every node ALSO gets the generic Inputs/Outputs/
// Timing tabs below, so this only covers the bespoke visualization (or a stub hint).
function DetailsTab({ node }: { node: VeNode }) {
  const type = node.type ?? ''
  if (type.endsWith('_source')) return <SourceSecondaryTab node={node} />
  if (type === 'dataset') return <DatasetSecondaryTab node={node} />
  if (JUDGE_TYPES.has(type)) return <JudgeSecondaryTab node={node} />
  if (EVAL_TYPES.has(type)) return <EvalSecondaryTab node={node} />
  if (type === 'cl_rule_eval') return <ClRuleEvalSecondaryTab node={node} />
  if (type === 'lm_engine') return <LMEngineSecondaryTab node={node} />
  if (type === 'cl_adversarial') return <ClAdversarialSecondaryTab node={node} />
  if (type === 'cl_rule_tree' || type === 'cl_semantic_tree') return <ClRuleTreeSecondaryTab node={node} />
  if (type === 'preprocessing') {
    return (
      <p className="empty-hint">
        Pass-through stub — no artifacts are extracted yet, so there's nothing to inspect here.
      </p>
    )
  }
  if (type === 'judge_prompt') {
    return (
      <p className="empty-hint">
        A metric preset (M1–M6) or a custom free-text judge. Edit its fields in the
        node/Inspector; a preset's exact prompt is resolved per item and shown in the
        downstream Judge node's secondary tab (per-item prompt + parsed output).
      </p>
    )
  }
  return <p className="empty-hint">No detail view for this node type.</p>
}

type TabKey = 'details' | 'inputs' | 'outputs' | 'timing'
const TABS: { key: TabKey; label: string }[] = [
  { key: 'details', label: 'Details' },
  { key: 'inputs', label: 'Inputs' },
  { key: 'outputs', label: 'Outputs' },
  { key: 'timing', label: 'Timing' },
]

export function SecondaryTabModal() {
  const nodeId = useActiveGraphStore((s) => s.secondaryTabNodeId)
  const node = useActiveGraphStore((s) => s.nodes.find((n) => n.id === s.secondaryTabNodeId))
  const close = useActiveGraphStore((s) => s.closeSecondaryTab)
  const modalWidth = usePrefsStore((s) => s.modalWidth)
  const modalHeight = usePrefsStore((s) => s.modalHeight)
  const setModalWidth = usePrefsStore((s) => s.setModalWidth)
  const setModalHeight = usePrefsStore((s) => s.setModalHeight)
  const [tab, setTab] = useState<TabKey>('details')

  if (!nodeId || !node) return null

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
        <div className="secondary-tab-strip" role="tablist">
          {TABS.map((t) => (
            <button
              key={t.key}
              role="tab"
              aria-selected={tab === t.key}
              className={`secondary-tab-btn${tab === t.key ? ' active' : ''}`}
              onClick={() => setTab(t.key)}
            >
              {t.label}
            </button>
          ))}
        </div>
        <div className="modal-body">
          {tab === 'details' && <DetailsTab node={node} />}
          {tab === 'inputs' && <NodeInputsTab node={node} />}
          {tab === 'outputs' && <NodeOutputsTab node={node} />}
          {tab === 'timing' && <NodeTimingTab node={node} />}
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
