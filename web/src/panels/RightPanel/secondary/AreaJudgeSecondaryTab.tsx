import { useActiveRunStore } from '../../../store/activeTab'
import type { VeNode } from '../../../store/graphStore'
import { DataValueView } from './DataValueView'

export function AreaJudgeSecondaryTab({ node }: { node: VeNode }) {
  const result = useActiveRunStore((s) => s.lastNodeResults[node.id])
  const values = (result?.outputs?.area_judge_result ?? {}) as Record<string, {
    rubric_id?: string
    selection?: { selected?: number; total?: number; coverage?: number }
    units?: Array<{ valid?: boolean; score?: number }>
  }>
  const items = Object.values(values)
  if (!items.length) {
    return <p className="empty-hint">Run this node to inspect unit-level scores and coverage.</p>
  }
  const units = items.flatMap((item) => item.units ?? [])
  const valid = units.filter((unit) => unit.valid)
  const scores = valid.map((unit) => unit.score).filter((score): score is number => typeof score === 'number')
  return (
    <div>
      <div className="secondary-summary">
        <div><strong>Rubric:</strong> {items[0]?.rubric_id}</div>
        <div><strong>Items:</strong> {items.length}</div>
        <div><strong>Valid units:</strong> {valid.length} / {units.length}</div>
        <div><strong>Average:</strong> {scores.length
          ? (scores.reduce((a, b) => a + b, 0) / scores.length).toFixed(2)
          : '—'}</div>
      </div>
      <DataValueView value={values} />
    </div>
  )
}
