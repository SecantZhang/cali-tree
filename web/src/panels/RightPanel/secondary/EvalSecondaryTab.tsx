import type { Edge } from '@xyflow/react'
import { useState } from 'react'
import {
  CartesianGrid, Legend, ResponsiveContainer, Scatter, ScatterChart, Tooltip, XAxis, YAxis,
} from 'recharts'
import { mediaUrl } from '../../../api/media'
import type { NodeResultOut } from '../../../api/runs'
import type { VeNode } from '../../../store/graphStore'
import { useActiveGraphStore, useActiveRunStore } from '../../../store/activeTab'

interface DimensionReport {
  judge_signal: string
  n: number
  spearman: number | null
  kendall: number | null
  mae: number | null
  qwk: number | null
  by_category: Record<string, Record<string, number | null>>
}

interface AlignedRow {
  item_id: string
  dimension: string
  human: number
  judge_raw: number
}

interface MetricsReport {
  n_items: number
  per_dimension: Record<string, DimensionReport>
  rows?: AlignedRow[]
}

// Cycled if there are more dimensions than colors — plenty distinct for the <= 9
// dimensions HUMAN_DIMENSIONS currently defines.
const SCATTER_COLORS = ['#8b5cf6', '#16a34a', '#f59e0b', '#ef4444', '#0ea5e9', '#ec4899']

interface DiagnosticEntry {
  dimension: string
  reason: string
  count: number
  example_item_ids: string[]
}

interface EvalMeta {
  warning?: string
  diagnostics?: DiagnosticEntry[]
}

function fmt(v: number | null): string {
  return v === null ? '—' : v.toFixed(3)
}

// Eval's own inputs (judge_result, labels) never carry a file path — neither
// Judge.run()'s result nor AggregatedHumanRecord has one. Rather than adding a `dataset`
// input socket to Eval purely for this display lookup (forcing a new edge in every
// workflow for something that's cosmetic, not part of the alignment computation), trace
// the already-wired graph backward from Eval, through the Judge node that feeds it, to
// the Dataset node upstream of it, and read that node's own cached `dataset` output —
// every node's last outputs are already available client-side in `lastNodeResults`
// (a flat map, not scoped to any one component) once a run has completed.
function findVideoPath(
  evalNodeId: string, itemId: string, edges: Edge[], lastNodeResults: Record<string, NodeResultOut>,
): string | null {
  const judgeEdges = edges.filter(
    (e) => e.target === evalNodeId && e.targetHandle === 'judge_result',
  )
  for (const je of judgeEdges) {
    const datasetEdge = edges.find((e) => e.target === je.source && e.targetHandle === 'dataset')
    if (!datasetEdge) continue
    const dataset = lastNodeResults[datasetEdge.source]?.outputs?.dataset as
      | Record<string, { output?: { output_video_path?: string } }>
      | undefined
    const path = dataset?.[itemId]?.output?.output_video_path
    if (path) return path
  }
  return null
}

export function EvalSecondaryTab({ node }: { node: VeNode }) {
  const lastResult = useActiveRunStore((s) => s.lastNodeResults[node.id])
  const partial = useActiveRunStore((s) => s.partialResults[node.id])
  const lastNodeResults = useActiveRunStore((s) => s.lastNodeResults)
  const edges = useActiveGraphStore((s) => s.edges)
  const [selectedItem, setSelectedItem] = useState<string | null>(null)

  // While the node is still running, a live batch-eval preview (if the Judge Node feeding
  // it has batch_size set and has completed at least one batch) is more useful than
  // nothing — falls back to the terminal, authoritative result once the node finishes.
  const isRunning = node.data.status === 'running'
  const active = isRunning && partial ? partial : lastResult

  if (!active) {
    return <p className="empty-hint">Run this node to see the metrics dashboard here.</p>
  }

  const report = active.outputs?.metrics_report as MetricsReport | undefined
  if (!report) {
    return <p className="empty-hint">No metrics report available.</p>
  }

  const meta = active.meta as EvalMeta | undefined
  const dims = Object.entries(report.per_dimension).filter(([, d]) => d.n > 0)

  const itemIds = report.rows ? Array.from(new Set(report.rows.map((r) => r.item_id))).sort() : []
  const activeItem = selectedItem ?? itemIds[0] ?? null
  const videoPath = activeItem ? findVideoPath(node.id, activeItem, edges, lastNodeResults) : null

  return (
    <div>
      {isRunning && partial && (
        <p className="empty-hint">Live preview — updates as the Judge Node completes batches.</p>
      )}
      <p>{report.n_items} aligned item(s).</p>
      {meta?.warning && <p className="meta-warning">{meta.warning}</p>}
      {dims.length === 0 && (
        <div>
          <p className="empty-hint">No dimensions had matched human + judge scores.</p>
          {meta?.diagnostics && meta.diagnostics.length > 0 && (
            <div className="eval-diagnostics">
              <p><strong>Why:</strong></p>
              <ul>
                {meta.diagnostics.map((d) => (
                  <li key={`${d.dimension}:${d.reason}`}>
                    <strong>{d.dimension}</strong>: {d.reason} ({d.count} item(s), e.g.{' '}
                    {d.example_item_ids.join(', ')})
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}
      {dims.length > 0 && report.rows && report.rows.length > 0 && (
        <div className="secondary-chart">
          <ResponsiveContainer width="100%" height={220}>
            <ScatterChart margin={{ top: 8, right: 8, bottom: 8, left: 0 }}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis type="number" dataKey="human" name="human" domain={[1, 5]} ticks={[1, 2, 3, 4, 5]} fontSize={11} />
              <YAxis type="number" dataKey="judge_raw" name="judge" domain={[1, 5]} ticks={[1, 2, 3, 4, 5]} fontSize={11} />
              <Tooltip cursor={{ strokeDasharray: '3 3' }} />
              <Legend />
              {dims.map(([dim], i) => (
                <Scatter
                  key={dim}
                  name={dim}
                  data={report.rows!.filter((r) => r.dimension === dim)}
                  fill={SCATTER_COLORS[i % SCATTER_COLORS.length]}
                />
              ))}
            </ScatterChart>
          </ResponsiveContainer>
        </div>
      )}
      {dims.length > 0 && (
        <table className="metrics-table">
          <thead>
            <tr>
              <th>Dimension</th>
              <th>n</th>
              <th>Spearman</th>
              <th>Kendall</th>
              <th>MAE</th>
              <th>QWK</th>
            </tr>
          </thead>
          <tbody>
            {dims.map(([dim, d]) => (
              <tr key={dim}>
                <td>{dim}</td>
                <td>{d.n}</td>
                <td>{fmt(d.spearman)}</td>
                <td>{fmt(d.kendall)}</td>
                <td>{fmt(d.mae)}</td>
                <td>{fmt(d.qwk)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      {itemIds.length > 0 && (
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
          <div className="item-preview">
            {videoPath ? (
              <video controls preload="metadata" className="item-video" src={mediaUrl(videoPath)} />
            ) : (
              <p className="empty-hint">
                No video found for this item (its Dataset node hasn't run, or the item has
                no rendered output).
              </p>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
