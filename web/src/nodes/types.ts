export type NodeStatus = 'idle' | 'queued' | 'running' | 'done' | 'error'

export interface VeNodeData extends Record<string, unknown> {
  params: Record<string, unknown>
  status: NodeStatus
  error?: string | null
  collapsed?: boolean
}
