import { useState } from 'react'
import { ProgressBar } from '../../../components/ProgressBar'
import type { VeNode } from '../../../store/graphStore'
import { useRunStore } from '../../../store/runStore'

interface JudgeMetricResult {
  parsed?: Record<string, unknown> | null
  valid?: boolean
  error?: string
  skipped?: boolean
}

export function JudgeSecondaryTab({ node }: { node: VeNode }) {
  const nodeResult = useRunStore((s) => s.lastNodeResults[node.id])
  const nodeProgress = useRunStore((s) => s.nodeProgress[node.id])
  const logs = useRunStore((s) => s.logs)
  const [selectedItem, setSelectedItem] = useState<string | null>(null)

  if (node.data.status === 'running') {
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

  if (!nodeResult) {
    return <p className="empty-hint">Run this node to see per-item rationale here.</p>
  }

  const judgeResult = (nodeResult.outputs?.judge_result ?? {}) as Record<
    string, Record<string, JudgeMetricResult>
  >
  const itemIds = Object.keys(judgeResult)

  if (itemIds.length === 0) {
    return <p className="empty-hint">No judge results yet (dry run, or zero items).</p>
  }

  const allResults = itemIds.flatMap((iid) => Object.values(judgeResult[iid]))
  const validCount = allResults.filter((r) => r.valid === true).length
  const invalidOrErrorCount = allResults.filter((r) => r.valid === false || r.error).length
  const scores = allResults
    .map((r) => r.parsed?.score_1_to_5)
    .filter((s): s is number => typeof s === 'number')
  const avgScore = scores.length ? scores.reduce((a, b) => a + b, 0) / scores.length : null

  const active = selectedItem ?? itemIds[0]
  const perMetric = judgeResult[active] ?? {}

  return (
    <div>
      <div className="secondary-summary">
        <div><strong>Items:</strong> {itemIds.length}</div>
        <div><strong>Valid calls:</strong> {validCount} / {allResults.length}</div>
        {invalidOrErrorCount > 0 && (
          <div className="rationale-error"><strong>Invalid/errored:</strong> {invalidOrErrorCount}</div>
        )}
        {avgScore !== null && <div><strong>Avg score:</strong> {avgScore.toFixed(2)} / 5</div>}
      </div>
      <div className="secondary-split">
        <ul className="dataset-item-list secondary-item-list">
          {itemIds.map((iid) => (
            <li
              key={iid} className={iid === active ? 'active' : ''}
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
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
