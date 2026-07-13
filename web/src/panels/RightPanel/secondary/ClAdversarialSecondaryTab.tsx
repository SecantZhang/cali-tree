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

// The upstream Judge Node's own result for this item, carried through unmodified as
// `DebateTranscript.initial_judge_result` (core.calibration.debate.schema) — this is
// the pre-debate baseline the whole debate starts from, never re-derived.
interface InitialJudgeResult {
  judge?: string
  metric_id?: string
  prompt_version?: string
  prompt_system?: string | null
  prompt_user?: string
  parsed?: Record<string, unknown> | null
  valid?: boolean
  validation_flags?: string[]
  model?: string | null
  promptTokens?: number | null
  completionTokens?: number | null
  totalTokens?: number | null
}

interface DebateTranscript {
  turns: DebateTurn[]
  converged: boolean
  convergence_reason?: string
  initial_judge_result?: InitialJudgeResult
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

// The debate's actual first message: the anchor Judge run it's reacting to. Rendered
// inside the same scrollable .debate-chat as the judge/human-proxy turns (not a
// separate block) so it reads as the true start of the conversation, not a footnote.
function AnchorBubble({ result }: { result: InitialJudgeResult | undefined }) {
  if (!result) return null
  const parsed = result.parsed
  const score = typeof parsed?.score_1_to_5 === 'number'
    ? parsed.score_1_to_5
    : typeof parsed?.overall_av_sync_score === 'number'
      ? parsed.overall_av_sync_score
      : undefined
  const lines = Array.isArray(parsed?.reasoning_lines) ? (parsed?.reasoning_lines as string[]) : []
  const flags = result.validation_flags ?? []
  const tokens = [
    result.promptTokens != null && `${result.promptTokens} prompt`,
    result.completionTokens != null && `${result.completionTokens} completion`,
    result.totalTokens != null && `${result.totalTokens} total`,
  ].filter(Boolean)

  return (
    <div className="debate-turn debate-turn-anchor">
      <div className="debate-turn-header">
        <span>Original judge run</span>
        {result.metric_id && <span className="tag">{result.metric_id}</span>}
        {typeof score === 'number' && <span className="tag">score {score}</span>}
        {result.model && <span className="tag">{result.model}</span>}
        {result.valid === false && <span className="tag tag-error">invalid</span>}
        {flags.map((f) => <span key={f} className="tag tag-error">{f}</span>)}
      </div>
      {lines.length > 0 && <p className="debate-turn-body">{lines.join(' ')}</p>}
      {tokens.length > 0 && <p className="debate-turn-tokens">tokens: {tokens.join(' / ')}</p>}
      {(result.prompt_system || result.prompt_user) && (
        <details>
          <summary>Prompt</summary>
          {result.prompt_system && (
            <>
              <p className="prompt-label">System</p>
              <pre className="json-preview">{result.prompt_system}</pre>
            </>
          )}
          {result.prompt_user && (
            <>
              <p className="prompt-label">User</p>
              <pre className="json-preview">{result.prompt_user}</pre>
            </>
          )}
        </details>
      )}
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
            <AnchorBubble result={item.transcript.initial_judge_result} />
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
