import { ParamField } from '../../nodes/ParamField'
import { NODE_PARAM_SCHEMAS } from '../../nodes/paramSchemas'
import { useActiveGraphStore } from '../../store/activeTab'

export function Inspector() {
  const selectedNodeId = useActiveGraphStore((s) => s.selectedNodeId)
  const node = useActiveGraphStore((s) => s.nodes.find((n) => n.id === s.selectedNodeId))
  const updateNodeParams = useActiveGraphStore((s) => s.updateNodeParams)

  if (!selectedNodeId || !node) {
    return <p className="empty-hint">Select a node to inspect its parameters.</p>
  }

  const schema = NODE_PARAM_SCHEMAS[node.type ?? ''] ?? {}
  const params = node.data.params
  const entries = Object.entries(schema)

  return (
    <div>
      <h3>{node.type}</h3>
      <p className="node-id">{node.id}</p>
      {node.data.locked && <p className="empty-hint">Locked — result reused; unlock to edit.</p>}
      {entries.length === 0 && <p className="empty-hint">This node has no parameters.</p>}
      <div className={node.data.locked ? 'params-locked' : undefined}>
        {entries.map(([key, field]) => (
          <ParamField
            // Scoped by node id, not just field name: this component stays mounted across a
            // node selection change, so a bare `key={key}` would reuse the same ParamField
            // instance (and its internal typing state, e.g. NumberParamField's `raw`) when
            // switching between two nodes of the same type that share a field name.
            key={`${node.id}-${key}`}
            name={key}
            field={field}
            value={params[key]}
            onChange={(v) => updateNodeParams(node.id, { [key]: v })}
          />
        ))}
      </div>
    </div>
  )
}
