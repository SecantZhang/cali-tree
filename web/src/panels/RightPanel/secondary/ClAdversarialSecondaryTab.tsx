import { useState } from 'react'
import { ProgressBar } from '../../../components/ProgressBar'
import type { VeNode } from '../../../store/graphStore'
import { useActiveRunStore } from '../../../store/activeTab'

interface DebateTurn {
  round: number
  role: 'judge' | 'human_proxy'
  parsed?: Record<string, unknown> | null
  valid?: boolean
  error?: string
  model?: string | null
  retrieval_used?: boolean
}

interface DebateTranscript {
  turns: DebateTurn[]
  converged: boolean
  convergence_reason?: string
}

interface CalibrationItem {
  item_id: string
  metric_id: string
  original_score: number | null
  final_score: number | null
  score_delta: number | null
  converged: boolean
  rounds_run: number
  flags: string[]
  optimized_prompt: string
  reasoning: string
  transcript: DebateTranscript
  human_scores: Record<string, number | null>
}

function DeltaBadge({ delta }: { delta: number | null }) {
  if (delta === null || Math.abs(delta) < 1e-9) return <span className="tag">unchanged</span>
  const cls = delta > 0 ? 'debate-delta-up' : 'debate-delta-down'
  const arrow = delta > 0 ? '▲' : '▼'
  return <span className={cls}>{arrow} {Math.abs(delta).toFixed(2)}</span>
}

function TurnBubble({ turn }: { turn: DebateTurn }) {
  const roleClass = turn.role === 'judge' ? 'debate-turn-judge' : 'debate-turn-human-proxy'
  const roleLabel = turn.role === 'judge' ? 'Judge' : 'Human proxy'
  const score = turn.parsed?.score_1_to_5
  const lines = Array.isArray(turn.parsed?.reasoning_lines)
    ? (turn.parsed?.reasoning_lines as string[])
    : []

  return (
    <div className={`debate-turn ${roleClass}`}>
      <div className="debate-turn-header">
        <span>{roleLabel}</span>
        <span className="tag">round {turn.round}</span>
        {typeof score === 'number' && <span className="tag">score {score}</span>}
        {turn.retrieval_used && <span className="tag">grounded</span>}
        {turn.valid === false && <span className="tag tag-error">invalid</span>}
        {turn.error && <span className="tag tag-error">error</span>}
      </div>
      {lines.length > 0 && <p className="debate-turn-body">{lines.join(' ')}</p>}
      {turn.error && <p className="rationale-error">{turn.error}</p>}
    </div>
  )
}

export function ClAdversarialSecondaryTab({ node }: { node: VeNode }) {
  const lastResult = useActiveRunStore((s) => s.lastNodeResults[node.id])
  const partial = useActiveRunStore((s) => s.partialResults[node.id])
  const nodeProgress = useActiveRunStore((s) => s.nodeProgress[node.id])
  const logs = useActiveRunStore((s) => s.logs)
  const [selectedItem, setSelectedItem] = useState<string | null>(null)

  const isRunning = node.data.status === 'running'
  const active = isRunning && partial ? partial : lastResult

  const calibrationResults = (active?.outputs?.calibration_results ?? {}) as Record<
    string, CalibrationItem
  >
  const itemIds = Object.keys(calibrationResults)

  if (itemIds.length === 0) {
    if (isRunning) {
      const lastLine = [...logs].reverse().find((l) => l.nodeId === node.id)
      return (
        <div>
          <ProgressBar
            progress={nodeProgress ?? { completed: 0, total: null }}
            label="Calibrating…"
          />
          {lastLine && <p className="empty-hint">{lastLine.text}</p>}
        </div>
      )
    }
    return (
      <p className="empty-hint">
        {active
          ? 'No calibration results yet (dry run, or zero items).'
          : 'Run this node to see per-item debate transcripts here.'}
      </p>
    )
  }

  const results = itemIds.map((iid) => calibrationResults[iid])
  const convergedCount = results.filter((r) => r.converged).length
  const deltas = results
    .map((r) => r.score_delta)
    .filter((d): d is number => typeof d === 'number')
  const avgAbsDelta = deltas.length
    ? deltas.reduce((a, b) => a + Math.abs(b), 0) / deltas.length
    : null

  const activeItem = selectedItem ?? itemIds[0]
  const item = calibrationResults[activeItem]
  const humanDims = Object.entries(item.human_scores ?? {})

  return (
    <div>
      {isRunning && partial && (
        <p className="empty-hint">Live preview — updates as this node completes batches.</p>
      )}
      <div className="secondary-summary">
        <div><strong>Items:</strong> {itemIds.length}</div>
        <div><strong>Converged:</strong> {convergedCount} / {itemIds.length}</div>
        {avgAbsDelta !== null && <div><strong>Avg |Δscore|:</strong> {avgAbsDelta.toFixed(2)}</div>}
      </div>
      <div className="secondary-split">
        <ul className="dataset-item-list secondary-item-list">
          {itemIds.map((iid) => {
            const r = calibrationResults[iid]
            return (
              <li
                key={iid} className={iid === activeItem ? 'active' : ''}
                onClick={() => setSelectedItem(iid)}
              >
                {iid} <DeltaBadge delta={r.score_delta} />{' '}
                {r.converged ? '✓' : '✕'}
              </li>
            )
          })}
        </ul>
        <div className="rationale-view">
          <div className="debate-score-strip">
            <div><strong>Original:</strong> {item.original_score ?? '—'}</div>
            <div><strong>Calibrated:</strong> {item.final_score ?? '—'}</div>
            <div><strong>Δ:</strong> <DeltaBadge delta={item.score_delta} /></div>
            {humanDims.length > 0 ? (
              humanDims.map(([dim, val]) => (
                <div key={dim}><strong>Human ({dim}):</strong> {val ?? '—'}</div>
              ))
            ) : (
              <div className="empty-hint">no human dimension for this metric</div>
            )}
            <div>
              <span className="tag">{item.converged ? 'converged' : 'not converged'}</span>{' '}
              <span className="tag">{item.rounds_run} round(s)</span>
              {item.flags.map((f) => (
                <span key={f} className="tag">{f}</span>
              ))}
            </div>
          </div>

          <div className="debate-chat">
            {item.transcript.turns.map((turn, i) => (
              <TurnBubble key={i} turn={turn} />
            ))}
          </div>

          <details>
            <summary>Calibrated reasoning</summary>
            <p className="reasoning">{item.reasoning}</p>
          </details>
          <details>
            <summary>Optimized prompt</summary>
            <pre className="json-preview">{item.optimized_prompt}</pre>
          </details>
        </div>
      </div>
    </div>
  )
}
