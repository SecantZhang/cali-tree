import type { NodeProgress } from '../store/runStore'

// Shared by the per-node bar (NodeChrome) and the top-bar overall/current-node bars
// (RunProgress) — one rendering, three states:
//   - determinate: `total` is known (the Judge Node reports it via judge_progress_init) —
//     a real percentage fill.
//   - indeterminate ("busy"): `progress` is set but `total` is null (Dataset/Eval run as one
//     atomic step with no sub-progress signal) — an animated sliding bar, honestly meaning
//     "running, no ETA".
//   - idle: `progress` is null — a flat, unfilled, non-animated track. Distinct from "busy"
//     on purpose: the top-bar bars stay visible between/before runs, and an idle run must
//     not look like an in-flight one.
export function ProgressBar({
  progress, label, className, inline,
}: {
  progress: NodeProgress | null
  label?: string
  className?: string
  // Lays the label and track on one row (label left, track fills the rest) instead of
  // stacking label-over-track — used by the top-bar bars so they read inline and align.
  inline?: boolean
}) {
  const idle = progress === null
  const pct = progress && progress.total
    ? Math.min(100, (progress.completed / progress.total) * 100)
    : null

  const wrapClass = [
    'progress-bar-wrap',
    idle && 'progress-bar-wrap-idle',
    inline && 'progress-bar-inline',
    className,
  ].filter(Boolean).join(' ')

  return (
    <div className={wrapClass}>
      {label && (
        <div className="progress-bar-label">
          <span className="progress-bar-label-text" title={label}>{label}</span>
          {pct !== null && (
            <span className="progress-bar-count">
              {progress!.completed}/{progress!.total}
            </span>
          )}
        </div>
      )}
      <div className="progress-bar-track">
        {idle ? (
          <div className="progress-bar-fill progress-bar-idle" />
        ) : pct === null ? (
          <div className="progress-bar-fill progress-bar-indeterminate" />
        ) : (
          <div className="progress-bar-fill" style={{ width: `${pct}%` }} />
        )}
      </div>
    </div>
  )
}
