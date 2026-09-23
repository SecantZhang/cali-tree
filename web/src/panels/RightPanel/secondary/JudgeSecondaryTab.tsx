import { useState } from 'react'
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { ProgressBar } from '../../../components/ProgressBar'
import type { VeNode } from '../../../store/graphStore'
import { useActiveRunStore } from '../../../store/activeTab'

interface JudgeMetricResult {
  parsed?: Record<string, unknown> | null
  valid?: boolean
  error?: string
  skipped?: boolean
  prompt_system?: string | null
  prompt_user?: string
}

const SCORE_BUCKETS = [1, 2, 3, 4, 5]

export function JudgeSecondaryTab({ node }: { node: VeNode }) {
  const lastResult = useActiveRunStore((s) => s.lastNodeResults[node.id])
  const partial = useActiveRunStore((s) => s.partialResults[node.id])
  const nodeProgress = useActiveRunStore((s) => s.nodeProgress[node.id])
  const logs = useActiveRunStore((s) => s.logs)
  const [selectedItem, setSelectedItem] = useState<string | null>(null)

  // While running, a live in-flight snapshot (populated every `batch_size` items via the
  // executor's on_batch -> partial_result path) is far more useful than a bare progress
  // bar — same "prefer partial while running, fall back once finished" pattern EvalSecondaryTab
  // already uses for its own live preview.
  const isRunning = node.data.status === 'running'
  const active = isRunning && partial ? partial : lastResult

  const judgeResult = (active?.outputs?.judge_result ?? {}) as Record<
    string, Record<string, JudgeMetricResult>
  >
  const itemIds = Object.keys(judgeResult)

  if (itemIds.length === 0) {
    if (isRunning) {
      const lastLine = [...logs].reverse().find((l) => l.nodeId === node.id)
      return (
        <div>
          <ProgressBar
            progress={nodeProgress ?? { completed: 0, total: null }}
            label="Judging…"
          />
          {lastLine && <p className="empty-hint">{lastLine.text}</p>}
        </div>
      )
    }
    return (
      <p className="empty-hint">
        {active ? 'No judge results yet (dry run, or zero items).' : 'Run this node to see per-item rationale here.'}
      </p>
    )
  }

  const allResults = itemIds.flatMap((iid) => Object.values(judgeResult[iid]))
  const validCount = allResults.filter((r) => r.valid === true).length
  const invalidOrErrorCount = allResults.filter((r) => r.valid === false || r.error).length
  const scores = allResults
    .map((r) => r.parsed?.score_1_to_5)
    .filter((s): s is number => typeof s === 'number')
  const avgScore = scores.length ? scores.reduce((a, b) => a + b, 0) / scores.length : null
  const histogram = SCORE_BUCKETS.map((score) => ({
    score: String(score),
    count: scores.filter((s) => Math.round(s) === score).length,
  }))

  const activeItem = selectedItem ?? itemIds[0]
  const perMetric = judgeResult[activeItem] ?? {}

  return (
    <div>
      {isRunning && partial && (
        <p className="empty-hint">Live preview — updates as this node completes batches.</p>
      )}
      <div className="secondary-summary">
        <div><strong>Items:</strong> {itemIds.length}</div>
        <div><strong>Valid calls:</strong> {validCount} / {allResults.length}</div>
        {invalidOrErrorCount > 0 && (
          <div className="rationale-error"><strong>Invalid/errored:</strong> {invalidOrErrorCount}</div>
        )}
        {avgScore !== null && <div><strong>Avg score:</strong> {avgScore.toFixed(2)} / 5</div>}
      </div>
      {scores.length > 0 && (
        <div className="secondary-chart">
          <ResponsiveContainer width="100%" height={120}>
            <BarChart data={histogram}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="score" label={{ value: 'score_1_to_5', position: 'insideBottom', offset: -2 }} fontSize={11} />
              <YAxis allowDecimals={false} fontSize={11} width={24} />
              <Tooltip />
              <Bar dataKey="count" fill="var(--node-vejudge)" />
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}
      <div className="secondary-split">
        <ul className="dataset-item-list secondary-item-list">
          {itemIds.map((iid) => (
            <li
              key={iid} className={iid === activeItem ? 'active' : ''}
              onClick={() => setSelectedItem(iid)}
            >
              {iid}
            </li>
          ))}
        </ul>
        <div className="rationale-view">
          {Object.entries(perMetric).map(([metricId, res]) => (
            <div key={metricId} className="rationale-card">
              <div className="rationale-header">
                <strong>{metricId}</strong>
                {res.skipped && <span className="tag">skipped</span>}
                {res.error && <span className="tag tag-error">error</span>}
                {res.valid === false && <span className="tag tag-error">invalid</span>}
              </div>
              {res.parsed && (
                <>
                  {typeof res.parsed.score_1_to_5 === 'number' && (
                    <div>score: {res.parsed.score_1_to_5}</div>
                  )}
                  {typeof res.parsed.overall_av_sync_score === 'number' && (
                    <div>overall: {res.parsed.overall_av_sync_score}</div>
                  )}
                  {Array.isArray(res.parsed.reasoning_lines) && (
                    <p className="reasoning">
                      {(res.parsed.reasoning_lines as string[]).join(' ')}
                    </p>
                  )}
                </>
              )}
              {res.error && <p className="rationale-error">{res.error}</p>}
              {(res.prompt_system || res.prompt_user) && (
                <details>
                  <summary>Prompt</summary>
                  {res.prompt_system && (
                    <>
                      <p className="prompt-label">System</p>
                      <pre className="json-preview">{res.prompt_system}</pre>
                    </>
                  )}
                  {res.prompt_user && (
                    <>
                      <p className="prompt-label">User</p>
                      <pre className="json-preview">{res.prompt_user}</pre>
                    </>
                  )}
                </details>
              )}
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
