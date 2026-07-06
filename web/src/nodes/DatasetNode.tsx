import { Handle, Position, type NodeProps } from '@xyflow/react'
import { useGraphStore } from '../store/graphStore'
import { useRunStore } from '../store/runStore'
import { NodeChrome } from './NodeChrome'
import { ParamField } from './ParamField'
import { NODE_PARAM_SCHEMAS } from './paramSchemas'
import { SOCKET_COLORS } from './socketTypes'
import type { VeNodeData } from './types'

const SCHEMA = NODE_PARAM_SCHEMAS.dataset

export function DatasetNode({ id, data }: NodeProps) {
  const d = data as VeNodeData
  const updateNodeParams = useGraphStore((s) => s.updateNodeParams)
  const toggleNodeCollapsed = useGraphStore((s) => s.toggleNodeCollapsed)
  const progress = useRunStore((s) => s.nodeProgress[id])
  const loader = String(d.params.loader ?? 'peanut_eval')

  return (
    <NodeChrome
      title="Dataset" color="var(--node-db)" status={d.status} error={d.error}
      collapsed={d.collapsed} onToggleCollapse={() => toggleNodeCollapsed(id)}
      progress={progress}
    >
      {d.collapsed ? (
        <div className="rf-node-param">loader: {loader}</div>
      ) : (
        Object.entries(SCHEMA).map(([key, field]) => (
          <ParamField
            key={key} name={key} field={field} value={d.params[key]}
            onChange={(v) => updateNodeParams(id, { [key]: v })}
          />
        ))
      )}
      <Handle
        type="source" position={Position.Right} id="dataset"
        style={{ top: '38%', background: SOCKET_COLORS.dataset }}
      />
      <Handle
        type="source" position={Position.Right} id="labels"
        style={{ top: '68%', background: SOCKET_COLORS.labels }}
      />
    </NodeChrome>
  )
}
