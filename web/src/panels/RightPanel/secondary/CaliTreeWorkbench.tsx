import { useMemo, useState } from 'react'
import { mediaUrl } from '../../../api/media'
import { useActiveRunStore } from '../../../store/activeTab'
import type { VeNode } from '../../../store/graphStore'

interface TreeNode {
  id: string
  level: number
  status: string
  children: string[]
  covered_ids: string[]
  validation_accuracy: number
  prompt: string
  components: Record<string, string[]>
}

interface MetricBlock {
  n?: number
  accuracy?: number | null
  balanced_accuracy?: number | null
  per_editor?: Record<string, { n: number; accuracy: number }>
  confusion?: Record<string, Record<string, number>>
  human_agreement?: Record<string, MetricBlock>
}

interface ConsensusCalibrator {
  version?: string
  levels?: string[]
  min_support?: number
  rules?: Record<string, {
    n?: number
    label?: string
    gain?: number
    base_accuracy?: number
    rule_accuracy?: number
  }>
  selection?: {
    baseline_accuracy?: number | null
    baseline_balanced_accuracy?: number | null
    selected_accuracy?: number | null
    selected_balanced_accuracy?: number | null
    selected_levels?: string[]
    selected_min_support?: number
  }
}

interface SelectiveMetric {
  n_total?: number
  n_accepted?: number
  n_abstained?: number
  coverage?: number
  minimum_support?: number
  accepted?: MetricBlock
  policy?: {
    version?: string
    editor_accuracy_threshold?: number
    editor_min_support?: number
    active_editors?: string[]
  }
}

const STATUS_COLORS: Record<string, string> = {
  leaf: '#7dd3fc',
  accepted: '#86efac',
  partial: '#fde68a',
  promoted: '#c4b5fd',
  rejected: '#fca5a5',
  global: '#f0abfc',
}

function AccuracyCard({ title, value }: { title: string; value?: MetricBlock }) {
  return (
    <div className="calitree-stat-card">
      <span>{title}</span>
      <strong>{value?.accuracy == null ? '—' : `${(value.accuracy * 100).toFixed(1)}%`}</strong>
      <small>
        balanced {value?.balanced_accuracy == null
          ? '—'
          : `${(value.balanced_accuracy * 100).toFixed(1)}%`}
        {' · '}n={value?.n ?? 0}
      </small>
    </div>
  )
}

function MetricDetails({ metric }: { metric?: MetricBlock }) {
  if (!metric) return null
  const labels = ['no', 'partial', 'yes']
  const distribution = (metric as MetricBlock & {
    prediction_distribution?: Record<string, number>
  }).prediction_distribution ?? {}
  return (
    <div className="calitree-metric-details">
      <table className="schema-table" aria-label="Cali-Tree confusion matrix">
        <thead>
          <tr><th>human \ predicted</th>{labels.map((label) => <th key={label}>{label}</th>)}</tr>
        </thead>
        <tbody>
          {labels.map((target) => (
            <tr key={target}>
              <td>{target}</td>
              {labels.map((prediction) => (
                <td key={prediction}>{metric.confusion?.[target]?.[prediction] ?? 0}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
      <div className="calitree-distribution">
        {labels.map((label) => <span key={label}>{label}: {distribution[label] ?? 0}</span>)}
      </div>
      <div className="calitree-distribution" aria-label="Accuracy by human agreement">
        {Object.entries(metric.human_agreement ?? {}).map(([bucket, row]) => (
          <span key={bucket}>
            {bucket}: {row.accuracy == null ? '—' : `${(row.accuracy * 100).toFixed(1)}%`}
            {' '}(n={row.n ?? 0})
          </span>
        ))}
      </div>
      <table className="schema-table" aria-label="Cali-Tree per-editor accuracy">
        <tbody>
          {Object.entries(metric.per_editor ?? {}).map(([editor, row]) => (
            <tr key={editor}>
              <td>{editor}</td><td>{(row.accuracy * 100).toFixed(1)}%</td><td>n={row.n}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function PromptTree({
  tree, selected, onSelect,
}: {
  tree: Record<string, unknown>
  selected: string | null
  onSelect: (id: string) => void
}) {
  const nodes = (tree.nodes ?? {}) as Record<string, TreeNode>
  const values = Object.values(nodes)
  const levels = new Map<number, TreeNode[]>()
  for (const node of values) {
    const list = levels.get(node.level ?? 0) ?? []
    list.push(node)
    levels.set(node.level ?? 0, list)
  }
  return (
    <div className="calitree-tree" aria-label="Cali-Tree hierarchy">
      {[...levels.entries()].sort(([a], [b]) => b - a).map(([level, levelNodes]) => (
        <div className="calitree-level" key={level}>
          <span className="calitree-level-label">L{level}</span>
          {levelNodes.sort((a, b) => a.id.localeCompare(b.id)).map((node) => (
            <button
              key={node.id}
              className={`calitree-tree-node${selected === node.id ? ' selected' : ''}`}
              style={{ borderColor: STATUS_COLORS[node.status] ?? 'var(--border)' }}
              onClick={() => onSelect(node.id)}
              title={node.id}
            >
              <strong>{node.status}</strong>
              <span>{node.covered_ids.length} cases</span>
              <small>{(node.validation_accuracy * 100).toFixed(0)}%</small>
            </button>
          ))}
        </div>
      ))}
    </div>
  )
}

export function CaliTreeWorkbench({ node }: { node: VeNode }) {
  const lastResult = useActiveRunStore((s) => s.lastNodeResults[node.id])
  const outputs = lastResult?.outputs as Record<string, unknown> | undefined
  const tree = (outputs?.prompt_tree ?? {}) as Record<string, unknown>
  const report = (outputs?.calitree_report ?? {}) as Record<string, any>
  const nodes = (tree.nodes ?? {}) as Record<string, TreeNode>
  const [selectedNode, setSelectedNode] = useState<string | null>(null)
  const [selectedCase, setSelectedCase] = useState<string | null>(null)
  const cases = (report.cases ?? {}) as Record<string, Record<string, unknown>>
  const predictions = (report.predictions ?? {}) as Record<string, Record<string, unknown>>
  const calibrator = (report.consensus_calibrator
    ?? report.conflict_policy?.consensus_calibrator
    ?? {}) as ConsensusCalibrator
  const selectiveTest = (report.selective?.test ?? {}) as SelectiveMetric
  const calibrationRules = Object.entries(calibrator.rules ?? {})
  const caseIds = useMemo(() => Object.keys(cases).sort(), [cases])
  const runningAccuracy = useMemo(() => {
    let correct = 0
    return caseIds.map((id, index) => {
      correct += Number(cases[id]?.target_label === predictions[id]?.label)
      return { id, accuracy: correct / (index + 1) }
    })
  }, [caseIds, cases, predictions])
  const caseId = selectedCase && cases[selectedCase] ? selectedCase : caseIds[0]
  const selected = selectedNode ? nodes[selectedNode] : undefined

  if (!lastResult) {
    return <p className="empty-hint">Run Cali-Tree Train to inspect its hierarchy and metrics.</p>
  }

  return (
    <div className="calitree-workbench">
      <div className="calitree-stats">
        <AccuracyCard title="Initial · train" value={report.initial?.train} />
        <AccuracyCard title="Initial · test" value={report.initial?.test} />
        <AccuracyCard title="TextGrad · train" value={report.textgrad?.train} />
        <AccuracyCard title="TextGrad · test" value={report.textgrad?.test} />
        <AccuracyCard title="Cali-Tree · train" value={report.calitree?.train} />
        <AccuracyCard title="Cali-Tree · test" value={report.calitree?.test} />
        <AccuracyCard title="Selective · test" value={selectiveTest.accepted} />
      </div>
      <div className="calitree-node-detail" aria-label="Selective calibration summary">
        <strong>Training-calibrated selective operating point</strong>
        <div>
          coverage {
            selectiveTest.coverage == null
              ? '—'
              : `${(selectiveTest.coverage * 100).toFixed(1)}%`
          } · accepted {selectiveTest.n_accepted ?? 0}/{selectiveTest.n_total ?? 0}
          {' · '}review/abstain {selectiveTest.n_abstained ?? 0}
          {' · '}minimum consensus support {selectiveTest.minimum_support ?? 3}
        </div>
        <div>
          active editors {
            selectiveTest.policy?.active_editors?.join(', ') || '—'
          } · training accuracy threshold {
            selectiveTest.policy?.editor_accuracy_threshold == null
              ? '—'
              : `${(selectiveTest.policy.editor_accuracy_threshold * 100).toFixed(0)}%`
          } · editor support ≥ {selectiveTest.policy?.editor_min_support ?? '—'}
        </div>
      </div>
      <section className="calitree-two-column">
        <div>
          <h3>Test diagnostics</h3>
          <MetricDetails metric={report.calitree?.test} />
        </div>
        <div>
          <h3>Running accuracy</h3>
          <div className="calitree-running-accuracy">
            {runningAccuracy.map((point) => (
              <div key={point.id} title={point.id}>
                <span style={{ width: `${point.accuracy * 100}%` }} />
                <small>{(point.accuracy * 100).toFixed(0)}%</small>
              </div>
            ))}
          </div>
        </div>
      </section>

      <section>
        <h3>Training-learned consensus calibration</h3>
        <div className="calitree-node-detail">
          <strong>{calibrator.version ?? 'not fitted'}</strong>
          <div>
            Internal validation: {
              calibrator.selection?.baseline_accuracy == null
                ? '—'
                : `${(calibrator.selection.baseline_accuracy * 100).toFixed(1)}%`
            } → {
              calibrator.selection?.selected_accuracy == null
                ? '—'
                : `${(calibrator.selection.selected_accuracy * 100).toFixed(1)}%`
            }
          </div>
          <div>
            Selected hierarchy: {
              calibrator.selection?.selected_levels?.join(' → ')
              || calibrator.levels?.join(' → ')
              || 'consensus only'
            } · minimum support {
              calibrator.selection?.selected_min_support
              ?? calibrator.min_support
              ?? '—'
            } · {calibrationRules.length} deployed rules
          </div>
          {calibrationRules.length > 0 && (
            <table className="schema-table" aria-label="Consensus calibration rules">
              <thead>
                <tr><th>Rule</th><th>Label</th><th>Support</th><th>Gain</th></tr>
              </thead>
              <tbody>
                {calibrationRules.map(([rule, value]) => (
                  <tr key={rule}>
                    <td>{rule}</td>
                    <td>{value.label ?? '—'}</td>
                    <td>{value.n ?? 0}</td>
                    <td>{value.gain == null ? '—' : `${(value.gain * 100).toFixed(1)} pp`}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </section>

      <section>
        <h3>Prompt hierarchy</h3>
        <PromptTree tree={tree} selected={selectedNode} onSelect={setSelectedNode} />
        {selected && (
          <div className="calitree-node-detail">
            <strong>{selected.id}</strong>
            <div>{selected.status} · {selected.covered_ids.length} cases · {(selected.validation_accuracy * 100).toFixed(1)}%</div>
            {Object.entries(selected.components ?? {}).map(([kind, values]) => (
              <div key={kind}><b>{kind}:</b> {values.join(' · ') || '—'}</div>
            ))}
            <details><summary>Prompt</summary><pre>{selected.prompt}</pre></details>
          </div>
        )}
      </section>

      <section className="calitree-two-column">
        <div>
          <h3>Timeline</h3>
          <ol className="calitree-timeline">
            {(report.timeline ?? []).map((event: Record<string, unknown>, index: number) => (
              <li key={`${String(event.node_id)}-${index}`}>
                <strong>{String(event.kind)}</strong> · {String(event.node_id)}
                {event.accuracy != null && ` · ${(Number(event.accuracy) * 100).toFixed(0)}%`}
              </li>
            ))}
          </ol>
        </div>
        <div>
          <h3>Usage</h3>
          <pre className="json-preview">{JSON.stringify(report.usage ?? {}, null, 2)}</pre>
          <div>Optimizer completion-token budget: {Number(report.optimizer_completion_token_budget ?? 0).toLocaleString()}</div>
        </div>
      </section>

      <section>
        <h3>Cases</h3>
        <div className="secondary-split">
          <ul className="dataset-item-list secondary-item-list">
            {caseIds.map((id) => (
              <li key={id} className={id === caseId ? 'active' : ''} onClick={() => setSelectedCase(id)}>
                {id} · {String(cases[id].target_label)} → {String(predictions[id]?.label ?? '—')}
              </li>
            ))}
          </ul>
          {caseId && (
            <div className="item-preview">
              <h4>{caseId}</h4>
              <div><strong>{String(cases[caseId].split)}</strong> · {String(cases[caseId].editor)}</div>
              <p>{String(cases[caseId].instruction)}</p>
              <div className="calitree-image-pair">
                <figure>
                  <img src={mediaUrl(String(cases[caseId].source_image_path))} alt="Source" />
                  <figcaption>Source</figcaption>
                </figure>
                <figure>
                  <img src={mediaUrl(String(cases[caseId].edited_image_path))} alt="Edited" />
                  <figcaption>Edited</figcaption>
                </figure>
              </div>
              <div><strong>Human:</strong> {String(cases[caseId].target_label)}</div>
              <div><strong>Cali-Tree:</strong> {String(predictions[caseId]?.label ?? '—')}</div>
              <div><strong>Route:</strong> {String(predictions[caseId]?.routed_node ?? '—')}</div>
              <p>{String(predictions[caseId]?.rationale ?? '')}</p>
            </div>
          )}
        </div>
      </section>
    </div>
  )
}
