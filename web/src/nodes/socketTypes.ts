// Static mirror of the backend's socket shapes (vejudge/interface/server/registry.py's
// NODE_EXECUTORS).

export type SocketType =
  | 'raw_dataset' | 'dataset' | 'labels' | 'engine_config' | 'judge_result' | 'metrics_report'

export const SOCKET_COLORS: Record<SocketType, string> = {
  raw_dataset: 'var(--node-db)',
  dataset: 'var(--node-db)',
  labels: 'var(--node-db)',
  engine_config: 'var(--node-vejudge)',
  judge_result: 'var(--node-vejudge)',
  metrics_report: 'var(--node-eval)',
}

export interface NodeTypeSockets {
  input: Record<string, SocketType>
  output: Record<string, SocketType>
}

export const NODE_SOCKETS: Record<string, NodeTypeSockets> = {
  peanut_source: { input: {}, output: { raw_dataset: 'raw_dataset' } },
  // `raw_dataset` is a distinct type from `dataset` specifically so a source's raw
  // output can never be wired directly into a Judge node — sampling is always explicit.
  // `labels` is looked up by item id against this node's own sampled items (not
  // independently re-sampled), so judge results and human labels always describe the
  // same items by construction.
  dataset: {
    input: { raw_dataset: 'raw_dataset' },
    output: { dataset: 'dataset', labels: 'labels' },
  },
  preprocessing: { input: { dataset: 'dataset' }, output: { dataset: 'dataset' } },
  lm_engine: { input: {}, output: { engine_config: 'engine_config' } },
  judge_text: {
    input: { dataset: 'dataset', engine_config: 'engine_config' },
    output: { judge_result: 'judge_result' },
  },
  judge_video: {
    input: { dataset: 'dataset', engine_config: 'engine_config' },
    output: { judge_result: 'judge_result' },
  },
  eval: {
    input: {
      judge_result_text: 'judge_result',
      judge_result_video: 'judge_result',
      labels: 'labels',
    },
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
