import { useActiveRunStore } from '../../../store/activeTab'
import type { VeNode } from '../../../store/graphStore'

interface MetricBlock {
  n?: number
  accuracy?: number | null
  balanced_accuracy?: number | null
  confusion?: Record<string, Record<string, number>>
}

interface SelectiveBlock {
  n_total?: number
  n_accepted?: number
  n_needs_human?: number
  n_abstained?: number
  needs_human_outcome_enabled?: boolean
  coverage?: number
  review_rate?: number
  error_capture_rate?: number | null
  partial_review_rate?: number | null
  system_accuracy_with_perfect_human_review?: number
  decision_distribution?: Record<string, number>
  accepted?: MetricBlock
}

interface CaliTreeMetricsReport {
  overall?: MetricBlock
  train?: MetricBlock
  test?: MetricBlock
  selective?: {
    overall?: SelectiveBlock
    train?: SelectiveBlock
    test?: SelectiveBlock
  }
}

const LABELS = ['no', 'partial', 'yes']

function percent(value?: number | null) {
  return value == null ? '—' : `${(value * 100).toFixed(1)}%`
}

function MetricCard({ title, metric }: { title: string; metric?: MetricBlock }) {
  return (
    <div className="calitree-stat-card">
      <span>{title}</span>
      <strong>{percent(metric?.accuracy)}</strong>
      <small>balanced {percent(metric?.balanced_accuracy)} · n={metric?.n ?? 0}</small>
    </div>
  )
}

export function CaliTreeEvalSecondaryTab({ node }: { node: VeNode }) {
  const lastResult = useActiveRunStore((state) => state.lastNodeResults[node.id])
  if (!lastResult) {
    return <p className="empty-hint">Run Cali-Tree Eval to inspect full and human-review metrics.</p>
  }
  const report = lastResult.outputs?.metrics_report as CaliTreeMetricsReport | undefined
  if (!report) {
    return <p className="empty-hint">No Cali-Tree metrics report available.</p>
  }
  const selective = report.selective?.overall
  return (
    <div className="calitree-workbench">
      <div className="calitree-stats">
        <MetricCard title="Full coverage · overall" metric={report.overall} />
        <MetricCard title="Full coverage · train" metric={report.train} />
        <MetricCard title="Full coverage · test" metric={report.test} />
        <MetricCard title="Auto-decided · overall" metric={selective?.accepted} />
      </div>

      {selective && (
        <section className="calitree-node-detail" aria-label="Human review metrics">
          <strong>
            {selective.needs_human_outcome_enabled
              ? 'Explicit needs_human outcome'
              : 'Available human-review operating point'}
          </strong>
          <div>
            auto coverage {percent(selective.coverage)}
            {' · '}auto-decided {selective.n_accepted ?? 0}/{selective.n_total ?? 0}
            {' · '}needs human {
              selective.n_needs_human ?? selective.n_abstained ?? 0
            } ({percent(selective.review_rate)})
          </div>
          <div>
            auto accuracy {percent(selective.accepted?.accuracy)}
            {' · '}error capture {percent(selective.error_capture_rate)}
            {' · '}partial sent to human {percent(selective.partial_review_rate)}
          </div>
          <div>
            Perfect-human-review system ceiling {
              percent(selective.system_accuracy_with_perfect_human_review)
            }; this is an upper bound, not model accuracy.
          </div>
          <div aria-label="Deployment decision distribution">
            decisions {['no', 'partial', 'yes', 'needs_human'].map((label) => (
              <span key={label}> · {label}: {selective.decision_distribution?.[label] ?? 0}</span>
            ))}
          </div>
        </section>
      )}

      <section>
        <h3>Full-coverage confusion matrix</h3>
        <table className="schema-table" aria-label="Cali-Tree Eval confusion matrix">
          <thead>
            <tr>
              <th>human \ predicted</th>
              {LABELS.map((label) => <th key={label}>{label}</th>)}
            </tr>
          </thead>
          <tbody>
            {LABELS.map((target) => (
              <tr key={target}>
                <td>{target}</td>
                {LABELS.map((prediction) => (
                  <td key={prediction}>
                    {report.overall?.confusion?.[target]?.[prediction] ?? 0}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </section>
    </div>
  )
}
