import type { ReactNode } from 'react'
import { useActiveGraphStore, useActiveRunStore } from '../store/activeTab'
import { NodeChrome } from './NodeChrome'
import { ParamField } from './ParamField'
import type { ParamField as ParamFieldSchema } from './paramSchemas'
import type { VeNodeData } from './types'

interface SimpleParamNodeProps {
  id: string
  data: VeNodeData
  selected?: boolean
  title: string
  color: string
  schema: Record<string, ParamFieldSchema>
  sockets: ReactNode
  // One-line text shown instead of the full param list once collapsed (only relevant
  // when `schema` is non-empty — a schema-less node like Eval never offers collapse).
  summaryLine?: (params: Record<string, unknown>) => string
  // Static body content for a node with no params at all (e.g. Eval) — shown unconditionally.
  staticBody?: ReactNode
}

/**
 * Shared shell for every node type that's just "sockets + a schema-driven param list" —
 * every concrete node file (PeanutSourceNode, DatasetNode, TextJudgeNode, ...) reduces to
 * supplying its title/color/schema/sockets. Collapsed-summary/param-mapping/status-
 * progress wiring live here once instead of being copied per node type.
 */
export function SimpleParamNode({
  id, data, selected, title, color, schema, sockets, summaryLine, staticBody,
}: SimpleParamNodeProps) {
  const updateNodeParams = useActiveGraphStore((s) => s.updateNodeParams)
  const toggleNodeCollapsed = useActiveGraphStore((s) => s.toggleNodeCollapsed)
  const progress = useActiveRunStore((s) => s.nodeProgress[id])
  const hasParams = Object.keys(schema).length > 0

  return (
    <NodeChrome
      title={title} color={color} status={data.status} error={data.error}
      collapsed={data.collapsed}
      onToggleCollapse={hasParams ? () => toggleNodeCollapsed(id) : undefined}
      progress={progress} selected={selected} sockets={sockets}
    >
      {!hasParams && staticBody}
      {hasParams && (
        data.collapsed ? (
          <div className="rf-node-param">{summaryLine ? summaryLine(data.params) : ''}</div>
        ) : (
          Object.entries(schema).map(([key, field]) => (
            <ParamField
              key={key} name={key} field={field} value={data.params[key]}
              onChange={(v) => updateNodeParams(id, { [key]: v })}
            />
          ))
        )
      )}
    </NodeChrome>
  )
}
