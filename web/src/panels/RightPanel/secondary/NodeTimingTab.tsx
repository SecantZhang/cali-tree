// Generic Timing tab — every node inherits it. Two views:
//  1) a whole-run WATERFALL: every node's run laid out by start offset + duration (this
//     node highlighted), from the centrally-stamped meta.elapsed_ms / meta.start_offset_ms.
//  2) a per-ITEM breakdown for loop nodes that report meta.item_timings (judge, calibration).
import {
  Bar,
  BarChart,
  Cell,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { nodeTitle } from '../../../nodes/nodeTitles'
import { useActiveGraphStore, useActiveRunStore } from '../../../store/activeTab'
import type { VeNode } from '../../../store/graphStore'

interface ItemTiming {
  item_id: string
  ms: number
}

function fmtMs(ms: number): string {
  return ms >= 1000 ? `${(ms / 1000).toFixed(2)}s` : `${Math.round(ms)}ms`
}

export function NodeTimingTab({ node }: { node: VeNode }) {
  const lastNodeResults = useActiveRunStore((s) => s.lastNodeResults)
  const nodes = useActiveGraphStore((s) => s.nodes)
  const typeById = new Map(nodes.map((n) => [n.id, n.type]))

  // --- whole-run waterfall from every timed node ---
  const waterfall = Object.entries(lastNodeResults)
    .map(([id, r]) => {
      const meta = (r?.meta ?? {}) as Record<string, unknown>
      const offset = typeof meta.start_offset_ms === 'number' ? meta.start_offset_ms : null
      const elapsed = typeof meta.elapsed_ms === 'number' ? meta.elapsed_ms : null
      return offset === null || elapsed === null
        ? null
        : { id, label: nodeTitle(typeById.get(id)), offset, elapsed, isThis: id === node.id }
    })
    .filter((r): r is NonNullable<typeof r> => r !== null)
    .sort((a, b) => a.offset - b.offset)

  const thisResult = lastNodeResults[node.id]
  const thisElapsed = (thisResult?.meta as Record<string, unknown> | undefined)?.elapsed_ms
  const itemTimings = ((thisResult?.meta as Record<string, unknown> | undefined)?.item_timings ??
    []) as ItemTiming[]
  const items = [...itemTimings].sort((a, b) => b.ms - a.ms).slice(0, 40)

  if (waterfall.length === 0) {
    return <p className="empty-hint">No timing yet — run the graph to see per-node timings.</p>
  }

  return (
    <div>
      <div className="secondary-summary">
        <div>
          <strong>This node:</strong>{' '}
          {typeof thisElapsed === 'number' ? fmtMs(thisElapsed) : '—'}
        </div>
        <div><strong>Nodes timed:</strong> {waterfall.length}</div>
      </div>

      <p className="schema-heading">Run waterfall (start offset → duration)</p>
      <ResponsiveContainer width="100%" height={Math.max(120, waterfall.length * 34)}>
        <BarChart layout="vertical" data={waterfall} margin={{ left: 8, right: 16, top: 4, bottom: 4 }}>
          <XAxis type="number" tickFormatter={fmtMs} fontSize={10} />
          <YAxis type="category" dataKey="label" width={120} fontSize={10} />
          <Tooltip
            formatter={(v, key) => [fmtMs(Number(v)), key === 'elapsed' ? 'duration' : 'offset']}
          />
          {/* transparent offset spacer + visible duration bar = a Gantt row */}
          <Bar dataKey="offset" stackId="t" fill="transparent" />
          <Bar dataKey="elapsed" stackId="t" radius={[2, 2, 2, 2]}>
            {waterfall.map((r) => (
              <Cell key={r.id} fill={r.isThis ? 'var(--accent)' : 'var(--border)'} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>

      {items.length > 0 && (
        <>
          <p className="schema-heading">
            Per-item breakdown ({itemTimings.length} items{itemTimings.length > 40 ? ', top 40' : ''})
          </p>
          <ResponsiveContainer width="100%" height={Math.max(120, items.length * 16)}>
            <BarChart layout="vertical" data={items} margin={{ left: 8, right: 16, top: 4, bottom: 4 }}>
              <XAxis type="number" tickFormatter={fmtMs} fontSize={10} />
              <YAxis type="category" dataKey="item_id" width={140} fontSize={9} />
              <Tooltip formatter={(v) => [fmtMs(Number(v)), 'duration']} />
              <Bar dataKey="ms" fill="var(--accent)" radius={[2, 2, 2, 2]} />
            </BarChart>
          </ResponsiveContainer>
        </>
      )}
    </div>
  )
}
