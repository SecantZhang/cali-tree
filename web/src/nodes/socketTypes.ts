// Static mirror of the backend's socket shapes (vejudge/interface/server/registry.py's
// NODE_EXECUTORS).

export type SocketType =
  | 'raw_dataset' | 'samples' | 'labels' | 'engine_config' | 'judge_spec' | 'judge_result'
  | 'metrics_report'

export const SOCKET_COLORS: Record<SocketType, string> = {
  raw_dataset: 'var(--node-db)',
  samples: 'var(--node-db)',
  labels: 'var(--node-db)',
  engine_config: 'var(--node-lm-engine)',
  judge_spec: 'var(--node-vejudge)',
  judge_result: 'var(--node-vejudge)',
  metrics_report: 'var(--node-eval)',
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
    input: { samples: 'samples', engine_config: 'engine_config', judge_spec: 'judge_spec' },
    output: { judge_result: 'judge_result' },
  },
  // One generic Eval node: it auto-scopes to whatever dimensions the incoming judge_result
  // covers (builtin metric via ALIGNMENT, or a custom judge's carried target dimension), so
  // each per-metric Judge path feeds straight into its own Eval node.
  eval: {
    input: { judge_result: 'judge_result', labels: 'labels' },
    output: { metrics_report: 'metrics_report' },
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
