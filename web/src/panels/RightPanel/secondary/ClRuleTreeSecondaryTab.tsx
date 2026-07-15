import { DecisionTreeView, type DecisionTreeNode } from '../../../components/DecisionTreeView'
import { ProgressBar } from '../../../components/ProgressBar'
import { useActiveRunStore } from '../../../store/activeTab'
import type { VeNode } from '../../../store/graphStore'
import { treeFeatureTooltip } from './treeFeatureTooltip'

interface BankEntry {
  question: string
  raises_score_when: string
}

interface JudgeRule {
  n_items?: number
  bank?: BankEntry[]
  feature_names?: string[]
  insample_mae?: Record<string, number | null>
  loo_mae?: Record<string, number | null>
  tree_rule?: string
  tree?: DecisionTreeNode | null
  per_item?: Record<string, { base: number; human: number; booleans: number[]; missing: string[] }>
}

const COMPARATORS: [string, string][] = [
  ['base', '(a) base only'],
  ['bias', '(b) base + global bias'],
  ['linear', '(c) linear[base+rules]'],
  ['tree', '(d) tree[base+rules]'],
]

function fmt(v: number | null | undefined): string {
  return v === null || v === undefined ? '—' : v.toFixed(2)
}

export function ClRuleTreeSecondaryTab({ node }: { node: VeNode }) {
  const lastResult = useActiveRunStore((s) => s.lastNodeResults[node.id])
  const partial = useActiveRunStore((s) => s.partialResults[node.id])
  const nodeProgress = useActiveRunStore((s) => s.nodeProgress[node.id])
  const isRunning = node.data.status === 'running'
  const active = isRunning && partial ? partial : lastResult
  const jr = (active?.outputs?.judge_rule ?? {}) as JudgeRule

  if (!jr.bank && !jr.per_item) {
    if (isRunning) {
      return <ProgressBar progress={nodeProgress ?? { completed: 0, total: null }} label="Mining rules…" />
    }
    return (
      <p className="empty-hint">
        {active
          ? 'No rule tree yet (dry run, or no usable items).'
          : 'Run this node to mine rules, fit the tree, and see in-sample vs held-out MAE.'}
      </p>
    )
  }

  const bank = jr.bank ?? []
  const perItem = Object.entries(jr.per_item ?? {})

  return (
    <div>
      <div className="secondary-summary">
        <div><strong>Items:</strong> {jr.n_items ?? perItem.length}</div>
        <div><strong>Rules:</strong> {bank.length}</div>
      </div>

      <p className="schema-heading">Mined decision rules (semantic booleans)</p>
      {bank.length > 0 ? (
        <ol className="engine-feeds-list">
          {bank.map((q, i) => (
            <li key={i}>
              q{i + 1}: {q.question} <span className="tag">raises when {q.raises_score_when}</span>
            </li>
          ))}
        </ol>
      ) : (
        <p className="empty-hint">No rules mined (the debates surfaced no reusable questions).</p>
      )}

      <p className="schema-heading">MAE vs human — does the rule tree beat a plain bias shift?</p>
      <table className="schema-table">
        <tbody>
          <tr><td className="schema-field">comparator</td><td className="schema-type">in-sample</td><td className="schema-type">held-out (LOO)</td></tr>
          {COMPARATORS.map(([key, label]) => (
            <tr key={key}>
              <td className="schema-desc">{label}</td>
              <td className="label-score">{fmt(jr.insample_mae?.[key])}</td>
              <td className="label-score">{fmt(jr.loo_mae?.[key])}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <p className="empty-hint">
        The rules add signal only if (c)/(d) held-out beats (b). In-sample at small n
        overfits — trust the LOO column.
      </p>

      {jr.tree ? (
        <>
          <p className="schema-heading">Fitted decision tree</p>
          <DecisionTreeView tree={jr.tree} featureTooltip={treeFeatureTooltip(bank)} />
          <p className="empty-hint">
            Splits read top-down; each leaf is the calibrated score (colored low→high) for
            items reaching it. Hover a split to see the mined rule behind it.
          </p>
          {jr.tree_rule && (
            <details>
              <summary>Raw rule (sklearn export)</summary>
              <pre className="json-preview">{jr.tree_rule}</pre>
            </details>
          )}
        </>
      ) : (
        jr.tree_rule && (
          <details open>
            <summary>Fitted decision tree</summary>
            <pre className="json-preview">{jr.tree_rule}</pre>
          </details>
        )
      )}

      <details>
        <summary>Per-item (base / human / rule answers)</summary>
        <table className="schema-table">
          <tbody>
            <tr>
              <td className="schema-field">item</td><td className="schema-type">base</td>
              <td className="schema-type">human</td><td className="schema-type">booleans</td>
            </tr>
            {perItem.map(([iid, r]) => (
              <tr key={iid}>
                <td className="schema-desc">{iid}</td>
                <td className="label-score">{r.base}</td>
                <td className="label-score">{r.human}</td>
                <td className="label-score">
                  [{r.booleans.join(', ')}]{r.missing.length > 0 && <span className="tag tag-error">missing {r.missing.length}</span>}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </details>
    </div>
  )
}
