// Generic Outputs tab — every node inherits it. Shows the raw value on each of the node's
// output sockets (from the run store), structured per NODE_SOCKETS[type].output. Live
// previews (partialResults) win while the node is running.
import { NODE_SOCKETS } from '../../../nodes/socketTypes'
import { useActiveRunStore } from '../../../store/activeTab'
import type { VeNode } from '../../../store/graphStore'
import { DataValueView } from './DataValueView'

export function NodeOutputsTab({ node }: { node: VeNode }) {
  const type = node.type ?? ''
  const lastResult = useActiveRunStore((s) => s.lastNodeResults[node.id])
  const partial = useActiveRunStore((s) => s.partialResults[node.id])
  const running = node.data.status === 'running'
  const outputs = (running && partial ? partial.outputs : lastResult?.outputs) ?? {}
  const sockets = NODE_SOCKETS[type]?.output ?? {}
  const socketNames = Object.keys(sockets)

  if (socketNames.length === 0) {
    return <p className="empty-hint">This node has no output sockets.</p>
  }
  const hasRun = lastResult || partial

  return (
    <div className="io-tab">
      {!hasRun && (
        <p className="empty-hint">No outputs yet — run this node to populate them.</p>
      )}
      {socketNames.map((name) => (
        <div className="io-socket" key={name}>
          <div className="io-socket-head">
            <span className="io-socket-name">{name}</span>
            <span className="tag">{sockets[name]}</span>
          </div>
          {name in outputs ? (
            <DataValueView value={outputs[name]} />
          ) : (
            <span className="empty-hint">no value</span>
          )}
        </div>
      ))}
    </div>
  )
}
