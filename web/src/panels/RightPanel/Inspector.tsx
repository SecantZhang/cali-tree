import { ParamField } from '../../nodes/ParamField'
import { NODE_PARAM_SCHEMAS } from '../../nodes/paramSchemas'
import { useGraphStore } from '../../store/graphStore'

export function Inspector() {
  const selectedNodeId = useGraphStore((s) => s.selectedNodeId)
  const node = useGraphStore((s) => s.nodes.find((n) => n.id === s.selectedNodeId))
  const updateNodeParams = useGraphStore((s) => s.updateNodeParams)

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
      {entries.length === 0 && <p className="empty-hint">This node has no parameters.</p>}
      {entries.map(([key, field]) => (
        <ParamField
          key={key}
          name={key}
          field={field}
          value={params[key]}
          onChange={(v) => updateNodeParams(node.id, { [key]: v })}
        />
      ))}
    </div>
  )
}
