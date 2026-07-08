import { ProgressBar } from '../../components/ProgressBar'
import { useActiveGraphStore, useActiveRunStore } from '../../store/activeTab'

const TITLE_FOR_TYPE: Record<string, string> = {
  peanut_source: 'Peanut Source',
  dataset: 'Dataset',
  preprocessing: 'Preprocessing',
  judge_text: 'Text Judge',
  judge_video: 'Video Judge',
  eval: 'Eval',
}

/**
 * Bars (b) and (c) from interface.md's Run controls section: overall workflow progress
 * (nodes completed / total), and directly below it, the currently-running node's own
 * progress — the same data driving that node's bar on the canvas (NodeChrome), just
 * also visible here so you don't need the node in view. Renders nothing while idle.
 */
export function RunProgress() {
  const status = useActiveRunStore((s) => s.status)
  const totalNodes = useActiveRunStore((s) => s.totalNodes)
  const completedCount = useActiveRunStore((s) => s.completedNodeIds.size)
  const currentRunningNodeId = useActiveRunStore((s) => s.currentRunningNodeId)
  const nodeProgress = useActiveRunStore((s) => s.nodeProgress)
  const currentNode = useActiveGraphStore((s) => s.nodes.find((n) => n.id === currentRunningNodeId))

  if (status !== 'running') return null

  const overall = { completed: completedCount, total: totalNodes || null }
  const current = currentRunningNodeId ? nodeProgress[currentRunningNodeId] : null
  const currentLabel = currentNode
    ? `${TITLE_FOR_TYPE[currentNode.type ?? ''] ?? currentNode.type} (${currentNode.id})`
    : null

  return (
    <div className="run-progress">
      <ProgressBar progress={overall} label="Workflow progress" />
      {current && currentLabel && (
        <ProgressBar progress={current} label={`Running: ${currentLabel}`} />
      )}
    </div>
  )
}
