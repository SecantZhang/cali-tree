import { Handle, Position, type NodeProps } from '@xyflow/react'
import { useGraphStore } from '../store/graphStore'
import { useRunStore } from '../store/runStore'
import { NodeChrome } from './NodeChrome'
import { ParamField } from './ParamField'
import { NODE_PARAM_SCHEMAS } from './paramSchemas'
import { SOCKET_COLORS } from './socketTypes'
import type { VeNodeData } from './types'

const SCHEMA = NODE_PARAM_SCHEMAS.judge

export function JudgeNode({ id, data }: NodeProps) {
  const d = data as VeNodeData
  const updateNodeParams = useGraphStore((s) => s.updateNodeParams)
  const toggleNodeCollapsed = useGraphStore((s) => s.toggleNodeCollapsed)
  const progress = useRunStore((s) => s.nodeProgress[id])
  const metrics = (d.params.metrics as string[] | null) ?? []

  return (
    <NodeChrome
      title="Judge" color="var(--node-vejudge)" status={d.status} error={d.error}
      collapsed={d.collapsed} onToggleCollapse={() => toggleNodeCollapsed(id)}
      progress={progress}
    >
      <Handle
        type="target" position={Position.Left} id="dataset"
        style={{ top: '50%', background: SOCKET_COLORS.dataset }}
      />
      {d.collapsed ? (
        <div className="rf-node-param">metrics: {metrics.length ? metrics.join(', ') : 'all'}</div>
      ) : (
        Object.entries(SCHEMA).map(([key, field]) => (
          <ParamField
            key={key} name={key} field={field} value={d.params[key]}
            onChange={(v) => updateNodeParams(id, { [key]: v })}
          />
        ))
      )}
      <Handle
        type="source" position={Position.Right} id="judge_result"
        style={{ top: '50%', background: SOCKET_COLORS.judge_result }}
      />
    </NodeChrome>
  )
}
