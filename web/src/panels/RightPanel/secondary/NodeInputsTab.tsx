// Generic Inputs tab — every node inherits it. Inputs aren't emitted by the backend, but a
// node's inputs ARE its upstream nodes' outputs: reconstruct them client-side from incoming
// edges + the run store (the same trick EvalSecondaryTab.findVideoPath uses, and what the
// executor itself does in _run_node), structured per NODE_SOCKETS[type].input. Fan-in
// sockets (MULTI_INPUT_SOCKETS) collect a list, matching the executor's merge.
import { MULTI_INPUT_SOCKETS, NODE_SOCKETS } from '../../../nodes/socketTypes'
import { useActiveGraphStore, useActiveRunStore } from '../../../store/activeTab'
import type { VeNode } from '../../../store/graphStore'
import { DataValueView } from './DataValueView'

export function NodeInputsTab({ node }: { node: VeNode }) {
  const type = node.type ?? ''
  const edges = useActiveGraphStore((s) => s.edges)
  const lastNodeResults = useActiveRunStore((s) => s.lastNodeResults)
  const sockets = NODE_SOCKETS[type]?.input ?? {}
  const multi = new Set(MULTI_INPUT_SOCKETS[type] ?? [])
  const socketNames = Object.keys(sockets)

  if (socketNames.length === 0) {
    return <p className="empty-hint">This node has no input sockets (it's a source).</p>
  }

  // For each input socket, the value(s) are the upstream node's output on the wired handle.
  const resolve = (socket: string): { value: unknown; wired: boolean } => {
    const incoming = edges.filter((e) => e.target === node.id && e.targetHandle === socket)
    if (incoming.length === 0) return { value: undefined, wired: false }
    const vals = incoming.map(
      (e) => lastNodeResults[e.source]?.outputs?.[e.sourceHandle ?? ''],
    )
    return { value: multi.has(socket) ? vals : vals[0], wired: true }
  }

  return (
    <div className="io-tab">
      <p className="empty-hint">
        Reconstructed from upstream outputs. Inputs seeded from a different locked/prior run
        show empty until that upstream runs here.
      </p>
      {socketNames.map((name) => {
        const { value, wired } = resolve(name)
        return (
          <div className="io-socket" key={name}>
            <div className="io-socket-head">
              <span className="io-socket-name">{name}</span>
              <span className="tag">{sockets[name]}</span>
              {multi.has(name) && <span className="tag">fan-in</span>}
            </div>
            {!wired ? (
              <span className="empty-hint">not connected</span>
            ) : (
              <DataValueView value={value} />
            )}
          </div>
        )
      })}
    </div>
  )
}
