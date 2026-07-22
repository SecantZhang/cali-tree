import { DecisionTreeView, type DecisionTreeNode } from '../../../components/DecisionTreeView'
import { ProgressBar } from '../../../components/ProgressBar'
import { useActiveRunStore } from '../../../store/activeTab'
import type { VeNode } from '../../../store/graphStore'
import { treeFeatureTooltip } from './treeFeatureTooltip'

interface BankEntry {
  question: string
  raises_score_when: string
  scope?: string
}

interface JudgeRule {
  n_items?: number
  n_observations?: number
  evaluation_mode?: string
  n_train_items?: number
  n_validation_items?: number
  n_prompt_tasks?: number
  n_judge_variants?: number
  metrics?: string[]
  warnings?: string[]
  dropped_features?: Array<{ question?: string; reason?: string }>
  diagnostics?: {
    n_raw_ratings?: number
    n_unique_base_scores?: number
    base_score_variance?: number
    score_source?: { parsed_field?: string }
    skipped_items?: Record<string, string>
  }
  bank?: BankEntry[]
  feature_names?: string[]
  insample_mae?: Record<string, number | null>
  loo_mae?: Record<string, number | null>
  tree_rule?: string
  tree?: DecisionTreeNode | null
  feature_labels?: Record<string, string>
  semantic_tree_selection?: {
    selected?: {
      feature_set?: string
      max_depth?: number
      min_samples_leaf?: number
      selection_reason?: string
      best_semantic_gain_over_base?: number | null
      semantic_gain_threshold?: number
      meaningful_decision_tree?: boolean
      semantic_or_prompt_splits?: string[]
      semantic_split_count?: number
      semantic_prompt_coverage?: number
      raw_score_split_count?: number
      semantic_coverage_tolerance?: number
      selected_cv_penalty_for_coverage?: number | null
    }
    training_grouped_loo?: Array<{ max_depth: number; min_samples_leaf: number; grouped_loo_mae: number | null }>
    validation_labels_used?: boolean
  }
  tree_architecture?: string
  semantic_split_count?: number
  raw_score_split_count?: number
  semantic_split_features?: string[]
  leaf_feature_names?: string[]
  per_item?: Record<string, {
    base: number
    human: number | number[]
    booleans: number[]
    semantic_values?: number[]
    missing: string[]
  }>
}

// Label + order for known comparators. The table renders whichever keys are actually
// present in the report (so the semantic-tree node's extra `semantic` row appears
// automatically, and the CART node stays four rows).
const COMPARATOR_LABELS: Record<string, string> = {
  base: '(a) base only',
  bias: '(b) base + global bias',
  score_linear: '(c) linear[base score only]',
  prompt_bias: '(d) base + prompt-specific bias',
  prompt_linear: '(e) linear[score distribution+prompt]',
  linear: '(f) linear[base+rules]',
  tree: '(g) tree[base+rules]',
  semantic: '(h) semantic model tree[semantic branches]',
}
const COMPARATOR_ORDER = [
  'base', 'bias', 'score_linear', 'prompt_bias', 'prompt_linear', 'linear', 'tree', 'semantic',
]

function comparatorKeys(jr: JudgeRule): string[] {
  const present = new Set([...Object.keys(jr.insample_mae ?? {}), ...Object.keys(jr.loo_mae ?? {})])
  const known = COMPARATOR_ORDER.filter((k) => present.has(k))
  const extra = [...present].filter((k) => !COMPARATOR_ORDER.includes(k)).sort()
  return [...known, ...extra]
}

function fmt(v: number | null | undefined): string {
  return v === null || v === undefined ? '—' : v.toFixed(2)
}

function fmt3(v: number | null | undefined): string {
  return v === null || v === undefined ? '—' : v.toFixed(3)
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
        <div><strong>Videos:</strong> {jr.n_items ?? perItem.length}</div>
        <div><strong>Raw ratings:</strong> {jr.n_observations ?? jr.diagnostics?.n_raw_ratings ?? '—'}</div>
        {jr.n_prompt_tasks !== undefined && <div><strong>Prompt tasks:</strong> {jr.n_prompt_tasks}</div>}
        {jr.n_judge_variants !== undefined && <div><strong>Judge variants:</strong> {jr.n_judge_variants}</div>}
        {(jr.metrics?.length ?? 0) > 0 && <div><strong>Prompts:</strong> {jr.metrics?.join(', ')}</div>}
        <div><strong>Rules:</strong> {bank.length}</div>
        <div><strong>Evaluation:</strong> {jr.evaluation_mode?.replaceAll('_', ' ') ?? 'legacy'}</div>
      </div>

      {(jr.warnings ?? []).map((warning, index) => (
        <p className="meta-warning" key={index}>{warning}</p>
      ))}
      <p className="empty-hint">
        Train/validation videos: {jr.n_train_items ?? '—'} / {jr.n_validation_items ?? '—'} · raw score field:{' '}
        {jr.diagnostics?.score_source?.parsed_field ?? '—'} · unique raw scores:{' '}
        {jr.diagnostics?.n_unique_base_scores ?? '—'}
      </p>

      {jr.semantic_tree_selection?.selected && (
        <>
          <p className="empty-hint">
            Semantic-tree capacity selected using training-only grouped LOO: depth{' '}
            {jr.semantic_tree_selection.selected.max_depth ?? '—'} · minimum leaf mass{' '}
            {jr.semantic_tree_selection.selected.min_samples_leaf ?? '—'} · feature set{' '}
            {jr.semantic_tree_selection.selected.feature_set?.replaceAll('_', ' ') ?? 'all'} · validation labels used for tuning:{' '}
            {jr.semantic_tree_selection.validation_labels_used ? 'yes' : 'no'}
          </p>
          {jr.semantic_tree_selection.selected.selection_reason === 'semantic_gain_below_threshold' && (
            <p className="empty-hint">
              Semantic capacity was rejected: its training-CV gain{' '}
              {fmt(jr.semantic_tree_selection.selected.best_semantic_gain_over_base)} was below the{' '}
              {fmt(jr.semantic_tree_selection.selected.semantic_gain_threshold)} threshold.
            </p>
          )}
          {jr.semantic_tree_selection.selected.meaningful_decision_tree && (
            <p className="empty-hint">
              Learned semantic decisions{' '}
              {jr.semantic_tree_selection.selected.semantic_or_prompt_splits?.join(', ') || '—'}.
            </p>
          )}
          <p className="empty-hint">
            Semantic-first structure: {jr.semantic_split_count ?? jr.semantic_tree_selection.selected.semantic_split_count ?? 0}{' '}
            learned semantic split(s) across{' '}
            {jr.semantic_tree_selection.selected.semantic_prompt_coverage ?? '—'} prompt context(s) ·{' '}
            {jr.raw_score_split_count ?? jr.semantic_tree_selection.selected.raw_score_split_count ?? 0} raw-score split(s).
            Score controls ({jr.leaf_feature_names?.join(', ') || 'none'}) are used only inside leaf calibration models.
          </p>
          {(jr.semantic_tree_selection.selected.selected_cv_penalty_for_coverage ?? 0) > 0 && (
            <p className="empty-hint">
              Broader semantic coverage cost{' '}
              {fmt3(jr.semantic_tree_selection.selected.selected_cv_penalty_for_coverage)} training-CV MAE,
              within the {fmt3(jr.semantic_tree_selection.selected.semantic_coverage_tolerance)} selection tolerance.
            </p>
          )}
        </>
      )}

      <p className="schema-heading">Decision features (graded semantics and debate rules)</p>
      {bank.length > 0 ? (
        <ol className="engine-feeds-list">
          {bank.map((q, i) => (
            <li key={i}>
              q{i + 1}: {q.question}{' '}
              {q.scope && <span className="tag">{q.scope.replaceAll('_', ' ')}</span>}{' '}
              <span className="tag">raises when {q.raises_score_when}</span>
            </li>
          ))}
        </ol>
      ) : (
        <p className="empty-hint">No rules mined (the debates surfaced no reusable questions).</p>
      )}

      <p className="schema-heading">Item-macro MAE vs human — does the rule tree beat a plain bias shift?</p>
      <table className="schema-table">
        <tbody>
          <tr><td className="schema-field">comparator</td><td className="schema-type">training</td><td className="schema-type">held-out</td></tr>
          {comparatorKeys(jr).map((key) => (
            <tr key={key}>
              <td className="schema-desc">{COMPARATOR_LABELS[key] ?? key}</td>
              <td className="label-score">{fmt(jr.insample_mae?.[key])}</td>
              <td className="label-score">{fmt(jr.loo_mae?.[key])}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <p className="empty-hint">
        Raw ratings remain separate targets but are weighted so each video contributes one
        unit. Frozen holdout mines rules from training videos only; legacy grouped LOO is exploratory.
      </p>

      {(jr.dropped_features?.length ?? 0) > 0 && (
        <details>
          <summary>Dropped constant questions ({jr.dropped_features?.length})</summary>
          <ul>{jr.dropped_features?.map((entry, index) => (
            <li key={index}>{entry.question ?? `q${index + 1}`} — {entry.reason}</li>
          ))}</ul>
        </details>
      )}

      {jr.tree ? (
        <>
          <p className="schema-heading">Fitted decision tree</p>
          <DecisionTreeView tree={jr.tree} featureTooltip={treeFeatureTooltip(bank, jr.feature_labels)} />
          <p className="empty-hint">
            Prompt nodes are fixed context routers. Every learned node below them is a semantic
            question; score values never create branches. A “model μ” leaf shows its mean fitted
            score, while its score-aware leaf model produces the actual prediction. Hover a split
            to see the mined rule behind it.
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
        <summary>Per-item (base / human / semantic evidence)</summary>
        <table className="schema-table">
          <tbody>
            <tr>
              <td className="schema-field">item</td><td className="schema-type">base</td>
              <td className="schema-type">human</td><td className="schema-type">semantic evidence</td>
            </tr>
            {perItem.map(([iid, r]) => (
              <tr key={iid}>
                <td className="schema-desc">{iid}</td>
                <td className="label-score">{r.base}</td>
                <td className="label-score">
                  {Array.isArray(r.human) ? `[${r.human.join(', ')}]` : r.human}
                </td>
                <td className="label-score">
                  [{(r.semantic_values ?? r.booleans).join(', ')}]
                  {r.missing.length > 0 && <span className="tag tag-error">missing {r.missing.length}</span>}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </details>
    </div>
  )
}
