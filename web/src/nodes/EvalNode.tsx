import { Handle, Position, type NodeProps } from '@xyflow/react'
import { useRunStore } from '../store/runStore'
import { NodeChrome } from './NodeChrome'
import { SOCKET_COLORS } from './socketTypes'
import type { VeNodeData } from './types'

export function EvalNode({ id, data }: NodeProps) {
  const d = data as VeNodeData
  const progress = useRunStore((s) => s.nodeProgress[id])

  return (
    <NodeChrome
      title="Eval" color="var(--node-eval)" status={d.status} error={d.error} progress={progress}
    >
      <Handle
        type="target" position={Position.Left} id="judge_result"
        style={{ top: '35%', background: SOCKET_COLORS.judge_result }}
      />
      <Handle
        type="target" position={Position.Left} id="labels"
        style={{ top: '65%', background: SOCKET_COLORS.labels }}
      />
      <div className="rf-node-param">human-vs-judge agreement</div>
      <Handle
        type="source" position={Position.Right} id="metrics_report"
        style={{ top: '50%', background: SOCKET_COLORS.metrics_report }}
      />
    </NodeChrome>
  )
}
