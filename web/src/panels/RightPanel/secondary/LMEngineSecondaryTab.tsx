import { useState } from 'react'
import { ApiError } from '../../../api/client'
import { checkEngineHealth, type EndpointHealth } from '../../../api/engines'
import { nodeTitle } from '../../../nodes/nodeTitles'
import { useActiveGraphStore } from '../../../store/activeTab'
import type { VeNode } from '../../../store/graphStore'

// The same real-call warning RunControls uses for a live run — a health check pings the
// gateway for real, so it gets the same confirm-before-call treatment.
const LIVE_CONFIRM =
  'This makes a real (billable) gateway call to each endpoint to test them. Continue with --live?'

export function LMEngineSecondaryTab({ node }: { node: VeNode }) {
  const params = node.data.params
  const engineKind = String(params.engine_kind ?? 'gpt')
  const model = (params.model as string | null) ?? null

  // Which Judge node(s) this engine's config feeds — traced off the live graph edges.
  const nodes = useActiveGraphStore((s) => s.nodes)
  const edges = useActiveGraphStore((s) => s.edges)
  const feeds = edges
    .filter((e) => e.source === node.id && e.sourceHandle === 'engine_config')
    .map((e) => {
      const target = nodes.find((n) => n.id === e.target)
      return { id: e.target, title: nodeTitle(target?.type) }
    })

  const [checking, setChecking] = useState(false)
  const [result, setResult] = useState<EndpointHealth[] | null>(null)
  const [error, setError] = useState<string | null>(null)

  const handleTest = async () => {
    if (!window.confirm(LIVE_CONFIRM)) return
    setChecking(true)
    setError(null)
    setResult(null)
    try {
      const res = await checkEngineHealth(engineKind, model, true)
      setResult(res.endpoints)
    } catch (e) {
      setError(e instanceof ApiError ? e.message : String(e))
    } finally {
      setChecking(false)
    }
  }

  return (
    <div>
      <div className="secondary-summary">
        <div><strong>Engine kind:</strong> {engineKind}</div>
        <div><strong>Model:</strong> {model || <em>default</em>}</div>
        <div><strong>Temperature:</strong> {String(params.temperature ?? '—')}</div>
        <div><strong>Max tokens:</strong> {String(params.max_tokens ?? '—')}</div>
        <div><strong>Concurrency:</strong> {String(params.concurrency ?? '—')}</div>
      </div>

      <div className="engine-feeds">
        <h5 className="schema-heading">Feeds</h5>
        {feeds.length === 0 ? (
          <p className="empty-hint">Not wired to any Judge node yet.</p>
        ) : (
          <ul className="engine-feeds-list">
            {feeds.map((f) => (
              <li key={f.id}>{f.title} <span className="mono-path">({f.id})</span></li>
            ))}
          </ul>
        )}
      </div>

      <div className="engine-health">
        <h5 className="schema-heading">Endpoint health</h5>
        <button className="btn-primary" onClick={handleTest} disabled={checking}>
          {checking ? 'Testing…' : 'Test this engine'}
        </button>
        {error && <p className="meta-warning">{error}</p>}
        {result && (
          <table className="engine-health-table">
            <tbody>
              {result.map((ep) => (
                <tr key={ep.url}>
                  <td>
                    <span className={`status-dot ${ep.ok ? 'status-done' : 'status-error'}`} />
                  </td>
                  <td className="mono-path">{ep.url}</td>
                  <td>{ep.status ?? '—'}</td>
                  <td>{ep.latency.toFixed(2)}s</td>
                  {ep.error && <td className="engine-health-error">{ep.error}</td>}
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      <p className="empty-hint engine-followup">
        A live tail of this engine's llm-histories.log slice (prompt hash, token counts,
        latency, retry/failover timeline) is still a planned future addition.
      </p>
    </div>
  )
}
