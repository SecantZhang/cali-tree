import { Handle, Position } from '@xyflow/react'

/**
 * One socket: the real, functional `<Handle>` plus a compact text label, both absolutely
 * positioned at the same `top` inside the node's `.rf-node-sockets` header zone (see
 * NodeChrome.tsx) — rendered as siblings, not nested, so the label never affects the
 * Handle's own hit-testing/connection-line geometry.
 */
export function SocketHandle({
  kind, id, label, top, color,
}: {
  kind: 'source' | 'target'
  id: string
  label: string
  top: string
  color: string
}) {
  const isTarget = kind === 'target'
  return (
    <>
      <Handle
        type={kind} position={isTarget ? Position.Left : Position.Right} id={id}
        style={{ top, background: color }}
      />
      <span
        className={`rf-node-socket-label ${isTarget ? 'rf-node-socket-label-left' : 'rf-node-socket-label-right'}`}
        style={{ top }}
      >
        {label}
      </span>
    </>
  )
}

/** top offsets for a side with any number of sockets, evenly stacked within the socket
 * zone (e.g. count=2 -> 33%/67%; count=3 -> 25%/50%/75%). */
export function socketTop(index: number, count: number): string {
  if (count <= 1) return '50%'
  return `${((index + 1) / (count + 1)) * 100}%`
}
