import { useActiveRunStore } from '../../../store/activeTab'
import type { VeNode } from '../../../store/graphStore'

interface Row {
  dimension: string
  n: number
  srcc: number | null
  plcc: number | null
  krcc: number | null
  mae: number | null
  human_ceiling_mae: number | null
}
interface Baseline {
  method: string
  kind: string
  srcc: number
  plcc: number
}
interface Comparison {
  rows?: Row[]
  verdict?: string
  baselines?: Baseline[]
  n_items?: number
}

function fmt(v: number | null | undefined): string {
  return v === null || v === undefined ? '—' : v.toFixed(3)
}

export function AlignmentReportSecondaryTab({ node }: { node: VeNode }) {
  const lastResult = useActiveRunStore((s) => s.lastNodeResults[node.id])
  const comp = (lastResult?.outputs?.comparison ?? {}) as Comparison

  if (!comp.rows) {
    return (
      <p className="empty-hint">
        {lastResult
          ? 'No report yet — wire an Eval node and run it on labeled items.'
          : 'Run the upstream Eval node to compute correlations, then this node frames them.'}
      </p>
    )
  }

  return (
    <div>
      <div className="secondary-summary">
        <div><strong>Items:</strong> {comp.n_items ?? '—'}</div>
      </div>
      {comp.verdict && (
        <p
          style={{
            borderLeft: '3px solid var(--node-eval)',
            padding: '8px 12px',
            margin: '8px 0',
            background: 'var(--surface-2, rgba(127,127,127,0.08))',
            borderRadius: 4,
          }}
        >
          {comp.verdict}
        </p>
      )}

      <p className="schema-heading">Our judge — human alignment</p>
      <table className="metrics-table">
        <thead>
          <tr>
            <th>Dimension</th><th>n</th>
            <th title="Spearman">SRCC</th><th title="Pearson">PLCC</th>
            <th title="Kendall">KRCC</th><th>MAE</th>
            <th title="Inter-rater mean |rater − item mean| — the noise floor">Human ceiling</th>
          </tr>
        </thead>
        <tbody>
          {comp.rows.map((r) => (
            <tr key={r.dimension}>
              <td>{r.dimension}</td><td>{r.n}</td>
              <td>{fmt(r.srcc)}</td><td>{fmt(r.plcc)}</td><td>{fmt(r.krcc)}</td>
              <td>{fmt(r.mae)}</td><td>{fmt(r.human_ceiling_mae)}</td>
            </tr>
          ))}
        </tbody>
      </table>

      <p className="schema-heading">VE-Bench published baselines (reference)</p>
      <table className="metrics-table">
        <thead>
          <tr><th>Method</th><th></th><th>SRCC</th><th>PLCC</th></tr>
        </thead>
        <tbody>
          {(comp.baselines ?? []).map((b) => (
            <tr key={b.method}>
              <td>{b.method}</td>
              <td><span className="tag">{b.kind}</span></td>
              <td>{b.srcc.toFixed(3)}</td>
              <td>{b.plcc.toFixed(3)}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <p className="empty-hint">
        Reference is VE-Bench's own table (human MOS, 1,170 edits). Compare our SRCC/PLCC row
        against these bands; VE-Bench QA is a metric trained on that data.
      </p>
    </div>
  )
}
