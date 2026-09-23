import { useEffect, useRef, useState } from 'react'
import { ProgressBar } from '../../../components/ProgressBar'
import type { VeNode } from '../../../store/graphStore'
import { useActiveRunStore } from '../../../store/activeTab'
import type { LiveDebate } from '../../../store/runStore'

const EMPTY_LIVE_DEBATES: Record<string, LiveDebate> = {}

interface DebateTurn {
  round: number
  role: 'judge' | 'human_proxy'
  parsed?: Record<string, unknown> | null
  valid?: boolean
  error?: string | null
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
  // Aggregated mode uses `score`; raw mode uses the unreduced `scores` list.
  human_scores: Record<string, { score: number | null; scores?: number[]; n: number }>
  // Always computed (independent of `grounded`/ground_in_human_labels) — raw
  // |final_score - human_score| per dimension/rating, no invented pass/fail threshold.
  human_gap: Record<string, number | number[] | null>
  // True when scalar or raw human evidence was available AND grounding was enabled.
  grounded: boolean
  summary_mode_requested?: 'llm' | 'rule_based'
  summary_mode_used?: 'llm' | 'rule_based' | 'rule_based_fallback'
  summary_version?: string
  summary_error?: string | null
  human_disagreement_profile?: {
    rating_count?: number
    histogram?: Record<string, number>
    range?: number
    median?: number
    modes?: number[]
    polarized?: boolean
    required_perspectives?: string[]
  }
  score_provenance?: {
    metric_id?: string
    parsed_field?: string
    raw_value?: number
    model?: string | null
    aggregation?: string
  }
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
  const liveDebates = useActiveRunStore((s) => s.liveDebates[node.id] ?? EMPTY_LIVE_DEBATES)
  const nodeProgress = useActiveRunStore((s) => s.nodeProgress[node.id])
  const logs = useActiveRunStore((s) => s.logs)
  const [selectedItem, setSelectedItem] = useState<string | null>(null)
  const chatRef = useRef<HTMLDivElement | null>(null)
  const followChatBottom = useRef(true)

  const isRunning = node.data.status === 'running'
  const liveItemIds = Object.keys(liveDebates)
  // A current-run partial remains the best available snapshot after this node becomes
  // done and a downstream node starts. Authoritative results replace it atomically when
  // the whole run is hydrated; a new live chat hides stale prior-run results meanwhile.
  const active = partial ?? (liveItemIds.length > 0 ? undefined : lastResult)

  const calibrationResults = (active?.outputs?.calibration_results ?? {}) as Record<
    string, CalibrationItem
  >
  const itemIds = Array.from(new Set([...liveItemIds, ...Object.keys(calibrationResults)]))

  useEffect(() => {
    if (itemIds.length === 0) {
      if (selectedItem !== null) setSelectedItem(null)
      return
    }
    if (selectedItem === null || !itemIds.includes(selectedItem)) {
      setSelectedItem(itemIds[0])
    }
  }, [itemIds.join('\u0000'), selectedItem])

  const results = Object.values(calibrationResults)
  const convergedCount = results.filter((r) => r.converged).length
  const deltas = results
    .map((r) => r.score_delta)
    .filter((d): d is number => typeof d === 'number')
  const avgAbsDelta = deltas.length
    ? deltas.reduce((a, b) => a + Math.abs(b), 0) / deltas.length
    : null

  const activeItem = selectedItem && itemIds.includes(selectedItem)
    ? selectedItem
    : (itemIds[0] ?? '')
  const item = calibrationResults[activeItem]
  const liveItem = liveDebates[activeItem]
  const transcript: DebateTranscript = item?.transcript ?? {
    turns: (liveItem?.turns ?? []) as DebateTurn[],
    converged: false,
    initial_judge_result: liveItem?.initial_judge_result as InitialJudgeResult | undefined,
  }
  const humanDims = Object.entries(item?.human_scores ?? {})
  const liveRunning = Object.values(liveDebates).some((debate) => debate.state === 'running')
  const nextRole = transcript.turns.at(-1)?.role === 'human_proxy' ? 'Judge' : 'Human proxy'
  const originalParsed = transcript.initial_judge_result?.parsed
  const liveOriginalScore = typeof originalParsed?.score_1_to_5 === 'number'
    ? originalParsed.score_1_to_5
    : typeof originalParsed?.overall_av_sync_score === 'number'
      ? originalParsed.overall_av_sync_score
      : null

  useEffect(() => {
    followChatBottom.current = true
  }, [activeItem])

  useEffect(() => {
    const chat = chatRef.current
    if (chat && followChatBottom.current) chat.scrollTop = chat.scrollHeight
  }, [activeItem, transcript.turns.length])

  const handleChatScroll = () => {
    const chat = chatRef.current
    if (!chat) return
    followChatBottom.current =
      chat.scrollHeight - chat.scrollTop - chat.clientHeight < 48
  }
  // One item-independent calibration note distilled across all items (node meta) — the
  // generalizing artifact, meant to be applied to unseen items.
  const generalPrompt =
    typeof active?.meta?.general_optimized_prompt === 'string'
      ? (active.meta.general_optimized_prompt as string)
      : ''

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

  return (
    <div>
      {(liveRunning || (isRunning && partial)) && (
        <p className="empty-hint">Live debate — updates after every completed agent turn.</p>
      )}
      <div className="secondary-summary">
        <div><strong>Items:</strong> {itemIds.length}</div>
        <div><strong>Converged:</strong> {convergedCount} / {itemIds.length}</div>
        {avgAbsDelta !== null && <div><strong>Avg |Δscore|:</strong> {avgAbsDelta.toFixed(2)}</div>}
      </div>
      {generalPrompt && (
        <details className="schema-details" open>
          <summary>General calibration prompt (applies across items)</summary>
          <pre className="json-preview">{generalPrompt}</pre>
        </details>
      )}
      <div className="secondary-split">
        <ul className="dataset-item-list secondary-item-list">
          {itemIds.map((iid) => {
            const r = calibrationResults[iid]
            const live = liveDebates[iid]
            return (
              <li
                key={iid} className={iid === activeItem ? 'active' : ''}
                onClick={() => setSelectedItem(iid)}
              >
                {iid}{' '}
                {r ? <DeltaBadge delta={r.score_delta} /> : <span className="tag">live</span>}{' '}
                {live?.state === 'running' ? '●' : r ? (r.converged ? '✓' : '✕') : '✓'}
              </li>
            )
          })}
        </ul>
        <div className="rationale-view">
          <div className="debate-score-strip">
            <div><strong>Original:</strong> {item?.original_score ?? liveOriginalScore ?? '—'}</div>
            {item?.score_provenance && (
              <div>
                <strong>Raw source:</strong> {item.score_provenance.parsed_field ?? '—'}
                {' = '}{item.score_provenance.raw_value ?? '—'}
              </div>
            )}
            <div><strong>Calibrated:</strong> {item?.final_score ?? 'debating…'}</div>
            {item && <div><strong>Δ:</strong> <DeltaBadge delta={item.score_delta} /></div>}
            {humanDims.length > 0 ? (
              humanDims.map(([dim, info]) => (
                <div key={dim}>
                  <strong>Human ({dim}):</strong>{' '}
                  {info.scores?.length ? info.scores.join(', ') : (info.score ?? '—')}{' '}
                  {info.n > 0 && <span className="tag">n={info.n}</span>}{' '}
                  {typeof item?.human_gap?.[dim] === 'number' && (
                    <span className="tag">gap {item.human_gap[dim].toFixed(2)}</span>
                  )}
                  {Array.isArray(item?.human_gap?.[dim]) && (
                    <span className="tag">
                      gaps {(item.human_gap[dim] as number[]).map((v) => v.toFixed(2)).join(', ')}
                    </span>
                  )}
                </div>
              ))
            ) : (
              item ? <div className="empty-hint">no human dimension for this metric</div> : null
            )}
            <div>
              {item ? (
                <>
                  <span className="tag">{item.converged ? 'converged' : 'not converged'}</span>{' '}
                  <span className="tag">{item.rounds_run} round(s)</span>{' '}
                </>
              ) : (
                <span className="tag">conversation in progress</span>
              )}{' '}
              {item?.grounded && <span className="tag">grounded</span>}
              {item?.summary_mode_used && (
                <span className={item.summary_mode_used === 'rule_based_fallback' ? 'tag tag-error' : 'tag'}>
                  summary: {item.summary_mode_used.replaceAll('_', ' ')}
                </span>
              )}
              {(item?.flags ?? []).map((f) => (
                <span key={f} className="tag">{f}</span>
              ))}
            </div>
          </div>

          <div className="debate-chat" ref={chatRef} onScroll={handleChatScroll}>
            <AnchorBubble result={transcript.initial_judge_result} />
            {transcript.turns.map((turn, i) => (
              <TurnBubble key={i} turn={turn} />
            ))}
            {liveItem?.state === 'running' && (
              <div className="debate-responding" aria-live="polite">
                <span className="debate-responding-dot" />
                {nextRole} responding…
              </div>
            )}
          </div>

          {item?.human_disagreement_profile?.rating_count && (
            <details open={item.human_disagreement_profile.polarized}>
              <summary>
                Fixed human disagreement profile
                {item.human_disagreement_profile.polarized ? ' — polarized' : ''}
              </summary>
              <pre className="json-preview">
                {JSON.stringify(item.human_disagreement_profile, null, 2)}
              </pre>
            </details>
          )}

          {item && (
            <>
              <details>
                <summary>Calibrated reasoning</summary>
                <p className="reasoning">{item.reasoning}</p>
              </details>
              <details>
                <summary>
                  Optimized prompt
                  {item.summary_version ? ` (${item.summary_version})` : ''}
                </summary>
                {item.summary_error && (
                  <p className="rationale-error">LLM summary fallback: {item.summary_error}</p>
                )}
                <pre className="json-preview">{item.optimized_prompt}</pre>
              </details>
            </>
          )}
        </div>
      </div>
    </div>
  )
}
