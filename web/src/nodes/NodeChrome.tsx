import { NodeResizer } from '@xyflow/react'
import type { ReactNode } from 'react'
import { ProgressBar } from '../components/ProgressBar'
import type { NodeProgress } from '../store/runStore'
import type { NodeStatus } from './types'

const MIN_NODE_WIDTH = 200
const MIN_NODE_HEIGHT = 120

// Small inline padlock glyphs (currentColor) — a crisp, theme-aware alternative to an emoji
// lock, matching the monochrome look of the ▶/↻/▾ header controls.
function LockGlyph({ open, size = 12 }: { open: boolean; size?: number }) {
  return (
    <svg viewBox="0 0 24 24" width={size} height={size} fill="none" stroke="currentColor"
      strokeWidth="2.6" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <rect x="4" y="11" width="16" height="10" rx="2" />
      {open ? <path d="M8 11V7a4 4 0 0 1 7.5-1.9" /> : <path d="M8 11V7a4 4 0 0 1 8 0v4" />}
    </svg>
  )
}

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
  // Overrides the zone's default 44px height (see .rf-node-sockets in App.css) — needed
  // by any node with more than ~3 sockets on one side: socketTop() spaces handles evenly
  // within this height, so packing e.g. 5 targets into 44px puts adjacent handles only a
  // few px apart, well within each other's hit-radius (confirmed via
  // document.elementFromPoint — a drag aimed at one handle's own computed center
  // resolved to its neighbor instead). Most node types don't need this.
  socketZoneHeight?: number
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
  // Locked: result frozen and reused on every run (see graphStore.lockNode). Shows a
  // padlock and a distinct border; params are rendered read-only by the caller.
  locked?: boolean
  // Run (▶): this node's full ancestor chain + itself, from scratch. Re-run (↻): just this
  // node, reusing the most recent run's outputs for everything upstream — disabled (with a
  // tooltip) when there's no prior run yet to reuse. Both omitted entirely for a node type
  // with no executable notion of "run" (there is none today, but keeps this optional).
  onRun?: () => void
  onRerun?: () => void
  runDisabledReason?: string | null
  rerunDisabledReason?: string | null
  // Lock/unlock toggle in the node header. Acts on the whole current selection (see
  // SimpleParamNode) — locking freezes results + predecessors, unlocking cascades forward.
  onToggleLock?: () => void
  lockDisabledReason?: string | null
  // Elapsed run time (ms) for a small on-node badge — shown live-ticking while running, then
  // the final backend-measured value once done (see SimpleParamNode). Generic across all
  // node types (executor stamps meta.elapsed_ms centrally).
  elapsedMs?: number | null
  children?: ReactNode
}

function fmtElapsed(ms: number): string {
  return ms >= 1000 ? `${(ms / 1000).toFixed(1)}s` : `${Math.round(ms)}ms`
}

export function NodeChrome({
  title, color, status, error, collapsed, onToggleCollapse, progress, sockets, selected,
  socketZoneHeight, orderIndex, stale, locked, onRun, onRerun, runDisabledReason,
  rerunDisabledReason, onToggleLock, lockDisabledReason, elapsedMs, children,
}: NodeChromeProps) {
  const running = status === 'running'
  return (
    <div
      className={`rf-node${running ? ' is-running' : ''}${stale ? ' is-stale' : ''}${locked ? ' is-locked' : ''}`}
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
        {locked && (
          <span className="rf-node-lock-badge" title="Locked — result frozen and reused on every run">
            <LockGlyph open={false} />
          </span>
        )}
        {stale && <span className="rf-node-stale-badge" title="An upstream node was re-run since this last ran">stale</span>}
        {typeof elapsedMs === 'number' && (
          <span
            className={`rf-node-time-badge${running ? ' is-running' : ''}`}
            title={running ? 'Elapsed (running)' : 'Last run time'}
          >
            {fmtElapsed(elapsedMs)}
          </span>
        )}
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
        {onToggleLock && (
          <button
            className={`node-run-btn node-lock-btn nodrag nopan${locked ? ' is-locked' : ''}`}
            onClick={onToggleLock}
            disabled={!locked && !!lockDisabledReason}
            title={
              locked
                ? 'Unlock this node (and everything downstream) — also unlocks the whole selection'
                : lockDisabledReason ??
                  'Lock: freeze this node + its predecessors and reuse their results on every run (applies to the whole selection)'
            }
            aria-label={locked ? 'Unlock node' : 'Lock node'}
          >
            {/* Icon reflects current state: open padlock when unlocked, closed when locked. */}
            <LockGlyph open={!locked} />
          </button>
        )}
      </div>
      <div className="rf-node-sockets" style={socketZoneHeight ? { height: socketZoneHeight } : undefined}>
        {sockets}
      </div>
      {running && <ProgressBar progress={progress ?? { completed: 0, total: null }} className="node-progress-bar" />}
      <div className="rf-node-body">{children}</div>
    </div>
  )
}
