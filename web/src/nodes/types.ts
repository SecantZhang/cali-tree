export type NodeStatus = 'idle' | 'queued' | 'running' | 'done' | 'error'

export interface VeNodeData extends Record<string, unknown> {
  params: Record<string, unknown>
  status: NodeStatus
  error?: string | null
  collapsed?: boolean
  // Captured on collapse (from the node's own width/height, however they got there —
  // manual NodeResizer drag or a loaded workflow's saved `size`) and restored on expand,
  // so collapsing a manually-resized node actually shrinks it instead of leaving the
  // outer chrome pinned to its last explicit pixel size (see toggleNodeCollapsed).
  expandedSize?: { width: number; height: number }
}
