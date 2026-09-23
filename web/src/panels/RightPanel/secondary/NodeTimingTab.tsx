// Generic Timing tab — every node inherits it. Two parts:
//   1) SYSTEM WATERFALL — the big picture: every node's run laid out by start offset +
//      duration (this node highlighted), from the centrally-stamped meta.start_offset_ms /
//      meta.elapsed_ms.
//   2) THIS NODE — the granular breakdown of the selected node's own run: per-item durations
//      (+ summary stats) for loop nodes that report meta.item_timings, else its total time
//      with a note that it's a single-phase node.
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

  // --- Part 1: whole-run waterfall from every timed node ---
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

  const thisMeta = (lastNodeResults[node.id]?.meta ?? {}) as Record<string, unknown>
  const thisElapsed = typeof thisMeta.elapsed_ms === 'number' ? thisMeta.elapsed_ms : null
  const itemTimings = (thisMeta.item_timings ?? []) as ItemTiming[]
  const items = [...itemTimings].sort((a, b) => b.ms - a.ms)
  const shown = items.slice(0, 40)

  if (waterfall.length === 0) {
    return <p className="empty-hint">No timing yet — run the graph to see per-node timings.</p>
  }

  const total = items.reduce((s, i) => s + i.ms, 0)
  const mean = items.length ? total / items.length : 0

  return (
    <div>
      {/* ---------- Part 1: system big picture ---------- */}
      <p className="schema-heading">System run waterfall</p>
      <p className="empty-hint">Every node by start offset → duration; this node highlighted.</p>
      <ResponsiveContainer width="100%" height={Math.max(120, waterfall.length * 34)}>
        <BarChart layout="vertical" data={waterfall} margin={{ left: 8, right: 16, top: 4, bottom: 4 }}>
          <XAxis type="number" tickFormatter={fmtMs} fontSize={10} />
          <YAxis type="category" dataKey="label" width={120} fontSize={10} />
          <Tooltip
            formatter={(v, key) => [fmtMs(Number(v)), key === 'elapsed' ? 'duration' : 'offset']}
          />
          <Bar dataKey="offset" stackId="t" fill="transparent" />
          <Bar dataKey="elapsed" stackId="t" radius={[2, 2, 2, 2]}>
            {waterfall.map((r) => (
              <Cell key={r.id} fill={r.isThis ? 'var(--accent)' : 'var(--border)'} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>

      {/* ---------- Part 2: this node's granular breakdown ---------- */}
      <p className="schema-heading">This node — detailed breakdown</p>
      <div className="secondary-summary">
        <div><strong>Total:</strong> {thisElapsed != null ? fmtMs(thisElapsed) : '—'}</div>
        {items.length > 0 && (
          <>
            <div><strong>Items:</strong> {items.length}</div>
            <div><strong>Mean/item:</strong> {fmtMs(mean)}</div>
            <div><strong>Slowest:</strong> {fmtMs(items[0].ms)}</div>
          </>
        )}
      </div>

      {items.length > 0 ? (
        <>
          <p className="empty-hint">
            Per-item run time{items.length > 40 ? ' (top 40 slowest)' : ''}.
          </p>
          <ResponsiveContainer width="100%" height={Math.max(120, shown.length * 16)}>
            <BarChart layout="vertical" data={shown} margin={{ left: 8, right: 16, top: 4, bottom: 4 }}>
              <XAxis type="number" tickFormatter={fmtMs} fontSize={10} />
              <YAxis type="category" dataKey="item_id" width={140} fontSize={9} />
              <Tooltip formatter={(v) => [fmtMs(Number(v)), 'duration']} />
              <Bar dataKey="ms" fill="var(--accent)" radius={[2, 2, 2, 2]} />
            </BarChart>
          </ResponsiveContainer>
        </>
      ) : (
        <p className="empty-hint">
          Single-phase node — it runs as one step (no per-item loop), so its total run time
          above is the full breakdown.
        </p>
      )}
    </div>
  )
}
