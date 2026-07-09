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
  // Jupyter-style execution-order badge (top-left): this node's 1-based position in the
  // most recently *launched* run's actual scope (runStore.runOrder) — omitted (no badge)
  // when this node wasn't part of that run at all, per the confirmed "most recent run's
  // actual scope" semantics (not a fixed graph-wide numbering).
  orderIndex?: number | null
  // True when this node's last real result predates a since-changed ancestor (see
  // runStore.staleNodeIds / graphTraversal.ts) — old result still shown, just flagged.
  stale?: boolean
  // Run (▶): this node's full ancestor chain + itself, from scratch. Re-run (↻): just this
  // node, reusing the most recent run's outputs for everything upstream — disabled (with a
  // tooltip) when there's no prior run yet to reuse. Both omitted entirely for a node type
  // with no executable notion of "run" (there is none today, but keeps this optional).
  onRun?: () => void
  onRerun?: () => void
  runDisabledReason?: string | null
  rerunDisabledReason?: string | null
  children?: ReactNode
}

export function NodeChrome({
  title, color, status, error, collapsed, onToggleCollapse, progress, sockets, selected,
  orderIndex, stale, onRun, onRerun, runDisabledReason, rerunDisabledReason, children,
}: NodeChromeProps) {
  const running = status === 'running'
  return (
    <div
      className={`rf-node${running ? ' is-running' : ''}${stale ? ' is-stale' : ''}`}
      style={{ borderColor: color }}
    >
      <NodeResizer
        minWidth={MIN_NODE_WIDTH} minHeight={MIN_NODE_HEIGHT} isVisible={selected}
        lineClassName="rf-node-resize-line" handleClassName="rf-node-resize-handle"
      />
      <div className="rf-node-header" style={{ background: color }}>
        {orderIndex != null && (
          <span className="rf-node-order-badge" title={`Node #${orderIndex} in the most recent run`}>
            [{orderIndex}]
          </span>
        )}
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
        {stale && <span className="rf-node-stale-badge" title="An upstream node was re-run since this last ran">stale</span>}
        <span className={`status-dot status-${status}`} title={error ?? status} />
        {onRun && (
          <button
            className="node-run-btn nodrag nopan"
            onClick={onRun}
            disabled={!!runDisabledReason}
            title={runDisabledReason ?? "Run: this node's full ancestor chain + itself, from scratch"}
            aria-label="Run node"
          >
            ▶
          </button>
        )}
        {onRerun && (
          <button
            className="node-run-btn nodrag nopan"
            onClick={onRerun}
            disabled={!!rerunDisabledReason}
            title={rerunDisabledReason ?? 'Re-run: just this node, reusing the last run’s upstream outputs'}
            aria-label="Re-run node"
          >
            ↻
          </button>
        )}
      </div>
      <div className="rf-node-sockets">{sockets}</div>
      {running && <ProgressBar progress={progress ?? { completed: 0, total: null }} className="node-progress-bar" />}
      <div className="rf-node-body">{children}</div>
    </div>
  )
}
