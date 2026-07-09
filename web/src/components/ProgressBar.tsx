import type { NodeProgress } from '../store/runStore'

// Shared by the per-node bar (NodeChrome) and the top-bar overall/current-node bars
// (RunProgress) — one rendering, two placements. Determinate when `total` is known
// (the Judge Node reports it via judge_progress_init); indeterminate otherwise
// (Dataset/Eval run as one atomic step with no sub-progress signal — an honest "busy"
// animation rather than a fake percentage).
export function ProgressBar({
  progress, label, className,
}: {
  progress: NodeProgress
  label?: string
  className?: string
}) {
  const pct = progress.total ? Math.min(100, (progress.completed / progress.total) * 100) : null

  return (
    <div className={`progress-bar-wrap${className ? ` ${className}` : ''}`}>
      {label && (
        <div className="progress-bar-label">
          {label}
          {pct !== null && (
            <span className="progress-bar-count">
              {progress.completed}/{progress.total}
            </span>
          )}
        </div>
      )}
      <div className="progress-bar-track">
        {pct === null ? (
          <div className="progress-bar-fill progress-bar-indeterminate" />
        ) : (
          <div className="progress-bar-fill" style={{ width: `${pct}%` }} />
        )}
      </div>
    </div>
  )
}
