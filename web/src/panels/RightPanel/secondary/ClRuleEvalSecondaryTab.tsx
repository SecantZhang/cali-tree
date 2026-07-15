import { useActiveRunStore } from '../../../store/activeTab'
import type { VeNode } from '../../../store/graphStore'

interface BankEntry {
  question: string
  raises_score_when: string
}

interface ComparisonRow {
  key: string
  label: string
  insample: number | null
  loo: number | null
}

interface Comparison {
  n_items?: number
  metric?: string
  rows?: ComparisonRow[]
  tree_rule?: string
  bank?: BankEntry[]
  verdict?: string
  beats_bias?: boolean
}

function fmt(v: number | null | undefined): string {
  return v === null || v === undefined ? '—' : v.toFixed(2)
}

export function ClRuleEvalSecondaryTab({ node }: { node: VeNode }) {
  const lastResult = useActiveRunStore((s) => s.lastNodeResults[node.id])
  const partial = useActiveRunStore((s) => s.partialResults[node.id])
  const isRunning = node.data.status === 'running'
  const active = isRunning && partial ? partial : lastResult
  const comp = (active?.outputs?.comparison ?? {}) as Comparison

  if (!comp.rows) {
    return (
      <p className="empty-hint">
        {active
          ? 'No comparison yet — wire this node to a Rule/Tree Calibration node that ran.'
          : 'Run the upstream Rule/Tree Calibration node to compute the comparison, then this node renders it.'}
      </p>
    )
  }

  const rows = comp.rows
  const bank = comp.bank ?? []

  return (
    <div>
      <div className="secondary-summary">
        <div><strong>Items:</strong> {comp.n_items ?? '—'}</div>
        <div><strong>Metric:</strong> {comp.metric ?? '—'}</div>
      </div>

      {comp.verdict && (
        <p
          style={{
            borderLeft: `3px solid ${comp.beats_bias ? 'var(--node-eval)' : 'var(--border)'}`,
            padding: '8px 12px',
            margin: '8px 0',
            background: 'var(--surface-2, rgba(127,127,127,0.08))',
            borderRadius: 4,
          }}
        >
          {comp.verdict}
        </p>
      )}

      <p className="schema-heading">MAE vs human — does the rule tree beat a plain bias shift?</p>
      <table className="schema-table">
        <tbody>
          <tr>
            <td className="schema-field">comparator</td>
            <td className="schema-type">in-sample</td>
            <td className="schema-type">held-out (LOO)</td>
          </tr>
          {rows.map((r) => (
            <tr key={r.key}>
              <td className="schema-desc">{r.label}</td>
              <td className="label-score">{fmt(r.insample)}</td>
              <td className="label-score">{fmt(r.loo)}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <p className="empty-hint">
        The rules add signal only if (c)/(d) held-out beats (b). In-sample at small n
        overfits — trust the LOO column.
      </p>

      {bank.length > 0 && (
        <>
          <p className="schema-heading">Mined decision rules (semantic booleans)</p>
          <ol className="engine-feeds-list">
            {bank.map((q, i) => (
              <li key={i}>
                q{i + 1}: {q.question} <span className="tag">raises when {q.raises_score_when}</span>
              </li>
            ))}
          </ol>
        </>
      )}

      {comp.tree_rule && (
        <details open>
          <summary>Fitted decision tree</summary>
          <pre className="json-preview">{comp.tree_rule}</pre>
        </details>
      )}
    </div>
  )
}
