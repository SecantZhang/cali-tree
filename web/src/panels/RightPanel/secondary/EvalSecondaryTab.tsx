import type { VeNode } from '../../../store/graphStore'
import { useRunStore } from '../../../store/runStore'

interface DimensionReport {
  judge_signal: string
  n: number
  spearman: number | null
  kendall: number | null
  mae: number | null
  qwk: number | null
  by_category: Record<string, Record<string, number | null>>
}

interface MetricsReport {
  n_items: number
  per_dimension: Record<string, DimensionReport>
}

interface EvalMeta {
  warning?: string
}

function fmt(v: number | null): string {
  return v === null ? '—' : v.toFixed(3)
}

export function EvalSecondaryTab({ node }: { node: VeNode }) {
  const nodeResult = useRunStore((s) => s.lastNodeResults[node.id])

  if (!nodeResult) {
    return <p className="empty-hint">Run this node to see the metrics dashboard here.</p>
  }

  const report = nodeResult.outputs?.metrics_report as MetricsReport | undefined
  if (!report) {
    return <p className="empty-hint">No metrics report available.</p>
  }

  const meta = nodeResult.meta as EvalMeta | undefined
  const dims = Object.entries(report.per_dimension).filter(([, d]) => d.n > 0)

  return (
    <div>
      <p>{report.n_items} aligned item(s).</p>
      {meta?.warning && <p className="meta-warning">{meta.warning}</p>}
      {dims.length === 0 && (
        <p className="empty-hint">No dimensions had matched human + judge scores.</p>
      )}
      {dims.length > 0 && (
        <table className="metrics-table">
          <thead>
            <tr>
              <th>Dimension</th>
              <th>n</th>
              <th>Spearman</th>
              <th>Kendall</th>
              <th>MAE</th>
              <th>QWK</th>
            </tr>
          </thead>
          <tbody>
            {dims.map(([dim, d]) => (
              <tr key={dim}>
                <td>{dim}</td>
                <td>{d.n}</td>
                <td>{fmt(d.spearman)}</td>
                <td>{fmt(d.kendall)}</td>
                <td>{fmt(d.mae)}</td>
                <td>{fmt(d.qwk)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  )
}
