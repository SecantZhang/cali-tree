import { SOCKET_COLORS, SOCKET_EXAMPLES, type SocketType } from '../../../nodes/socketTypes'
import { DataValueView } from './DataValueView'

// Compact I/O contract header shown at the top of the generic Inputs/Outputs tabs. Lists every
// socket as `name: type` with a color swatch + a fan-in tag, and — when a representative example
// exists for that socket type — an expandable (collapsed-by-default) example payload so the
// contract reads as real JSON with its subfields, not just a bare type name. Sourced (by the
// caller) from the backend node-type API, so it covers every current/future node automatically.
export function SocketSchema({
  title,
  sockets,
  multi,
}: {
  title: string
  sockets: Record<string, string>
  multi?: Set<string>
}) {
  const names = Object.keys(sockets)
  return (
    <div className="socket-schema">
      <div className="socket-schema-title">{title}</div>
      {names.length === 0 ? (
        <span className="empty-hint">none</span>
      ) : (
        <ul className="socket-schema-list">
          {names.map((name) => {
            const socketType = sockets[name]
            // A brand-new socket type may not have a color yet — fall back to a neutral border.
            const color = SOCKET_COLORS[socketType as SocketType] ?? 'var(--border)'
            const example = SOCKET_EXAMPLES[socketType as SocketType]
            return (
              <li className="socket-schema-row" key={name}>
                <div className="socket-schema-head">
                  <span className="socket-schema-swatch" style={{ background: color }} />
                  <span className="socket-schema-name">{name}</span>
                  <span className="socket-schema-sep">:</span>
                  <span className="tag">{socketType}</span>
                  {multi?.has(name) && <span className="tag">fan-in</span>}
                </div>
                {example !== undefined && (
                  <div className="socket-schema-example">
                    <DataValueView value={example} />
                  </div>
                )}
              </li>
            )
          })}
        </ul>
      )}
    </div>
  )
}
