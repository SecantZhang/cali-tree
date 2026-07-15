// Static mirror of the backend's socket shapes (vejudge/interface/server/registry.py's
// NODE_EXECUTORS).

export type SocketType =
  | 'raw_dataset' | 'samples' | 'labels' | 'engine_config' | 'judge_spec' | 'judge_result'
  | 'metrics_report' | 'calibration_results' | 'general_calibration' | 'judge_rule'

export const SOCKET_COLORS: Record<SocketType, string> = {
  raw_dataset: 'var(--node-db)',
  samples: 'var(--node-db)',
  labels: 'var(--node-db)',
  engine_config: 'var(--node-lm-engine)',
  judge_spec: 'var(--node-vejudge)',
  judge_result: 'var(--node-vejudge)',
  metrics_report: 'var(--node-eval)',
  calibration_results: 'var(--node-calibration)',
  general_calibration: 'var(--node-calibration)',
  judge_rule: 'var(--node-calibration)',
}

export interface NodeTypeSockets {
  input: Record<string, SocketType>
  output: Record<string, SocketType>
}

export const NODE_SOCKETS: Record<string, NodeTypeSockets> = {
  peanut_source: { input: {}, output: { raw_dataset: 'raw_dataset' } },
  // `raw_dataset` is a distinct type from `samples` specifically so a source's raw
  // output can never be wired directly into a Judge node — sampling is always explicit.
  // `labels` is looked up by item id against this node's own sampled items (not
  // independently re-sampled), so judge results and human labels always describe the
  // same items by construction. The sampled-item output is named `samples`, not
  // `dataset` — that name collided with the node's own name and its sibling `labels`
  // output, making the two easy to conflate.
  dataset: {
    input: { raw_dataset: 'raw_dataset' },
    output: { samples: 'samples', labels: 'labels' },
  },
  preprocessing: { input: { samples: 'samples' }, output: { samples: 'samples' } },
  lm_engine: { input: {}, output: { engine_config: 'engine_config' } },
  // A metric is now a wired artifact, not a dropdown: the Judge Prompt node emits a
  // `judge_spec` (a builtin M1-M6 preset, or a custom free-text judge) that the generic
  // Judge node consumes alongside samples + engine.
  judge_prompt: { input: {}, output: { judge_spec: 'judge_spec' } },
  judge: {
    input: {
      samples: 'samples', engine_config: 'engine_config', judge_spec: 'judge_spec',
      // Optional: a cl_adversarial node's per-item calibrated results. When wired, each
      // item's own optimized_prompt is injected for that item's judge call only.
      calibration: 'calibration_results',
      // Optional: a cl_adversarial node's item-independent corpus note, applied to every
      // item's judge call (dataset-wide).
      general_calibration: 'general_calibration',
    },
    output: { judge_result: 'judge_result' },
  },
  // One generic Eval node: it auto-scopes to whatever dimensions the incoming judge_result
  // covers (builtin metric via ALIGNMENT, or a custom judge's carried target dimension), so
  // each per-metric Judge path feeds straight into its own Eval node.
  eval: {
    input: { judge_result: 'judge_result', labels: 'labels' },
    output: { metrics_report: 'metrics_report' },
  },
  // A bounded judge-vs-human-proxy debate over a dataset — produces a per-item
  // calibrated result (its own transcript, distilled reasoning, and an `optimized_prompt`
  // addendum), not one aggregate prompt for the whole dataset. `labels` is optional (used
  // only for the secondary tab's judge-vs-human score comparison).
  cl_adversarial: {
    input: {
      samples: 'samples', judge_result: 'judge_result', labels: 'labels',
      judge_engine: 'engine_config', human_engine: 'engine_config',
    },
    output: {
      calibration_results: 'calibration_results',
      general_calibration: 'general_calibration',
    },
  },
  // Mines reusable decision rules from an upstream cl_adversarial node's debates, has an
  // independent critic answer them per item, and fits a decision tree [base + booleans]
  // -> human score. Fit+report (in-sample + LOO MAE); terminal `judge_rule` output.
  cl_rule_tree: {
    input: {
      samples: 'samples', calibration_results: 'calibration_results', labels: 'labels',
      critic_engine: 'engine_config',
    },
    output: { judge_rule: 'judge_rule' },
  },
  // A standalone eval node that re-surfaces a Rule/Tree Calibration node's `judge_rule`
  // report — the four-way MAE table (in-sample + held-out LOO), the mined rule bank, the
  // fitted tree, and a verdict on whether the rules beat a plain bias correction held-out.
  // Pure display (makes no calls); mirrors the Eval node's read-a-report role.
  cl_rule_eval: {
    input: { judge_rule: 'judge_rule' },
    output: { comparison: 'metrics_report' },
  },
}

export function isValidSocketConnection(
  sourceNodeType: string | undefined,
  sourceHandle: string | null | undefined,
  targetNodeType: string | undefined,
  targetHandle: string | null | undefined,
): boolean {
  if (!sourceNodeType || !targetNodeType || !sourceHandle || !targetHandle) return false
  const sourceSocket = NODE_SOCKETS[sourceNodeType]?.output[sourceHandle]
  const targetSocket = NODE_SOCKETS[targetNodeType]?.input[targetHandle]
  return !!sourceSocket && !!targetSocket && sourceSocket === targetSocket
}
