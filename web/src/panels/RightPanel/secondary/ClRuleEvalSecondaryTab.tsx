import { DecisionTreeView, type DecisionTreeNode } from '../../../components/DecisionTreeView'
import { useActiveRunStore } from '../../../store/activeTab'
import type { VeNode } from '../../../store/graphStore'
import { treeFeatureTooltip } from './treeFeatureTooltip'

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
  tree?: DecisionTreeNode | null
  bank?: BankEntry[]
  verdict?: string
  beats_bias?: boolean
  evaluation_mode?: string
  n_validation_items?: number
  warnings?: string[]
  improvement_ci_95?: number[]
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
        <div><strong>Videos:</strong> {comp.n_items ?? '—'}</div>
        <div><strong>Metric:</strong> {comp.metric ?? '—'}</div>
        <div><strong>Evaluation:</strong> {comp.evaluation_mode?.replaceAll('_', ' ') ?? 'legacy'}</div>
        <div><strong>Validation:</strong> {comp.n_validation_items ?? '—'}</div>
      </div>

      {(comp.warnings ?? []).map((warning, index) => (
        <p className="meta-warning" key={index}>{warning}</p>
      ))}

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

      <p className="schema-heading">Item-macro MAE vs human — calibration and incremental rule signal</p>
      <table className="schema-table">
        <tbody>
          <tr>
            <td className="schema-field">comparator</td>
            <td className="schema-type">training</td>
            <td className="schema-type">held-out</td>
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
        A positive claim requires frozen holdout, at least five validation videos, an MAE
        improvement of at least 0.05, and a paired 95% bootstrap interval above zero.
        Rule value is tested separately against score-only linear calibration.
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

      {comp.tree ? (
        <>
          <p className="schema-heading">Fitted decision tree</p>
          <DecisionTreeView tree={comp.tree} featureTooltip={treeFeatureTooltip(bank)} />
          <p className="empty-hint">
            Splits read top-down; each leaf is the calibrated score (colored low→high) for
            items reaching it. Hover a split to see the mined rule behind it.
          </p>
          {comp.tree_rule && (
            <details>
              <summary>Raw rule (sklearn export)</summary>
              <pre className="json-preview">{comp.tree_rule}</pre>
            </details>
          )}
        </>
      ) : (
        comp.tree_rule && (
          <details open>
            <summary>Fitted decision tree</summary>
            <pre className="json-preview">{comp.tree_rule}</pre>
          </details>
        )
      )}
    </div>
  )
}
