import type { ReactNode } from 'react'
import { ProgressBar } from '../components/ProgressBar'
import type { NodeProgress } from '../store/runStore'
import type { NodeStatus } from './types'

interface NodeChromeProps {
  title: string
  color: string
  status: NodeStatus
  error?: string | null
  collapsed?: boolean
  onToggleCollapse?: () => void
  progress?: NodeProgress
  children?: ReactNode
}

export function NodeChrome({
  title, color, status, error, collapsed, onToggleCollapse, progress, children,
}: NodeChromeProps) {
  const running = status === 'running'
  return (
    <div className={`rf-node${running ? ' is-running' : ''}`} style={{ borderColor: color }}>
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
      {running && <ProgressBar progress={progress ?? { completed: 0, total: null }} className="node-progress-bar" />}
      <div className="rf-node-body">{children}</div>
    </div>
  )
}
