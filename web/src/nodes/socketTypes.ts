// Static mirror of the backend's socket shapes (vejudge/interface/server/registry.py's
// NODE_EXECUTORS). Only the 3 in-scope node types exist — see interface.md.

export type SocketType = 'dataset' | 'labels' | 'judge_result' | 'metrics_report'

export const SOCKET_COLORS: Record<SocketType, string> = {
  dataset: 'var(--node-db)',
  labels: 'var(--node-db)',
  judge_result: 'var(--node-vejudge)',
  metrics_report: 'var(--node-eval)',
}

export interface NodeTypeSockets {
  input: Record<string, SocketType>
  output: Record<string, SocketType>
}

export const NODE_SOCKETS: Record<string, NodeTypeSockets> = {
  dataset: { input: {}, output: { dataset: 'dataset', labels: 'labels' } },
  judge: { input: { dataset: 'dataset' }, output: { judge_result: 'judge_result' } },
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
