import { NodeResizer } from '@xyflow/react'
import type { ReactNode } from 'react'
import { ProgressBar } from '../components/ProgressBar'
import type { NodeProgress } from '../store/runStore'
import type { NodeStatus } from './types'

const MIN_NODE_WIDTH = 200
const MIN_NODE_HEIGHT = 120

interface NodeChromeProps {
  title: string
  color: string
  status: NodeStatus
  error?: string | null
  collapsed?: boolean
  onToggleCollapse?: () => void
  progress?: NodeProgress
  // Every input/output Handle + its label (see SocketHandle.tsx) — rendered in a fixed-
  // height zone dedicated purely to connections, distinct from the params body below.
  sockets?: ReactNode
  // Drives NodeResizer's visibility — only show resize handles on the selected node, the
  // same convention React Flow examples use, so idle nodes don't clutter the canvas.
  selected?: boolean
  children?: ReactNode
}

export function NodeChrome({
  title, color, status, error, collapsed, onToggleCollapse, progress, sockets, selected,
  children,
}: NodeChromeProps) {
  const running = status === 'running'
  return (
    <div className={`rf-node${running ? ' is-running' : ''}`} style={{ borderColor: color }}>
      <NodeResizer
        minWidth={MIN_NODE_WIDTH} minHeight={MIN_NODE_HEIGHT} isVisible={selected}
        lineClassName="rf-node-resize-line" handleClassName="rf-node-resize-handle"
      />
      <div className="rf-node-header" style={{ background: color }}>
        {onToggleCollapse && (
          <button
            className="node-collapse-btn nodrag nopan"
            onClick={onToggleCollapse}
            title={collapsed ? 'Expand' : 'Collapse'}
            aria-label={collapsed ? 'Expand node' : 'Collapse node'}
          >
            {collapsed ? '▸' : '▾'}
          </button>
        )}
        <span className="rf-node-title">{title}</span>
        <span className={`status-dot status-${status}`} title={error ?? status} />
      </div>
      <div className="rf-node-sockets">{sockets}</div>
      {running && <ProgressBar progress={progress ?? { completed: 0, total: null }} className="node-progress-bar" />}
      <div className="rf-node-body">{children}</div>
    </div>
  )
}
