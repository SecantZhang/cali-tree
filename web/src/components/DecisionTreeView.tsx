// Renders a fitted shallow decision tree (from a Rule/Tree Calibration node) as an actual
// SVG node/edge diagram instead of sklearn's export_text string. Splits are drawn as
// condition boxes ("feature ≤ threshold"), leaves as score chips colored by the calibrated
// value (low = warm/red, high = cool/green), with the true/false branches labeled. The tree
// is tiny by construction (max_depth 2 → ≤ 7 nodes), so a simple leaf-slot layout is plenty.

export interface DecisionTreeNode {
  leaf: boolean
  samples: number
  value: number
  feature?: string
  threshold?: number
  left?: DecisionTreeNode
  right?: DecisionTreeNode
  context_router?: boolean
  semantic_decision?: boolean
  leaf_model?: { feature_names?: string[] }
}

interface Placed {
  id: number
  x: number // leaf-slot units (fractional for internal nodes)
  depth: number
  node: DecisionTreeNode
}
interface PlacedEdge {
  from: number
  to: number
  label: string
}

const COL_W = 150
const ROW_H = 96
const NODE_W = 124
const NODE_H = 52

// Map a 1–5 calibrated score to a hue (red→green) so leaf value reads at a glance.
function leafColors(value: number): { fill: string; stroke: string } {
  const t = Math.max(0, Math.min(1, (value - 1) / 4))
  const hue = Math.round(t * 120) // 0 = red, 120 = green
  return { fill: `hsl(${hue} 65% 90%)`, stroke: `hsl(${hue} 55% 45%)` }
}

function layout(root: DecisionTreeNode): {
  nodes: Placed[]
  edges: PlacedEdge[]
  maxDepth: number
  maxSlot: number
} {
  const nodes: Placed[] = []
  const edges: PlacedEdge[] = []
  let nextId = 0
  let nextLeafSlot = 0
  let maxDepth = 0

  function place(node: DecisionTreeNode, depth: number): Placed {
    const id = nextId++
    maxDepth = Math.max(maxDepth, depth)
    if (node.leaf || !node.left || !node.right) {
      const p: Placed = { id, x: nextLeafSlot++, depth, node }
      nodes.push(p)
      return p
    }
    const l = place(node.left, depth + 1)
    const r = place(node.right, depth + 1)
    const p: Placed = { id, x: (l.x + r.x) / 2, depth, node }
    nodes.push(p)
    edges.push({ from: id, to: l.id, label: 'true' })
    edges.push({ from: id, to: r.id, label: 'false' })
    return p
  }

  place(root, 0)
  return { nodes, edges, maxDepth, maxSlot: Math.max(0, nextLeafSlot - 1) }
}

export function DecisionTreeView({
  tree,
  featureTooltip,
}: {
  tree: DecisionTreeNode
  featureTooltip?: (feature: string) => string | undefined
}) {
  const { nodes, edges, maxDepth, maxSlot } = layout(tree)
  const byId = new Map(nodes.map((n) => [n.id, n]))
  const width = (maxSlot + 1) * COL_W
  const height = (maxDepth + 1) * ROW_H
  const cx = (n: Placed) => n.x * COL_W + COL_W / 2
  const cy = (n: Placed) => n.depth * ROW_H + ROW_H / 2

  return (
    <svg
      viewBox={`0 0 ${width} ${height}`}
      width={width}
      height={height}
      style={{ maxWidth: '100%', height: 'auto', display: 'block', fontFamily: 'inherit' }}
      role="img"
      aria-label="Fitted decision tree"
    >
      {/* edges first so nodes paint on top */}
      {edges.map((e, i) => {
        const from = byId.get(e.from)!
        const to = byId.get(e.to)!
        const x1 = cx(from)
        const y1 = cy(from) + NODE_H / 2
        const x2 = cx(to)
        const y2 = cy(to) - NODE_H / 2
        const mx = (x1 + x2) / 2
        const my = (y1 + y2) / 2
        return (
          <g key={`e${i}`}>
            <line x1={x1} y1={y1} x2={x2} y2={y2} stroke="var(--border)" strokeWidth={1.5} />
            <rect
              x={mx - 20}
              y={my - 9}
              width={40}
              height={18}
              rx={9}
              fill="var(--surface)"
              stroke="var(--border)"
            />
            <text
              x={mx}
              y={my}
              textAnchor="middle"
              dominantBaseline="central"
              fontSize={10}
              fill="var(--text-muted)"
            >
              {e.label}
            </text>
          </g>
        )
      })}

      {nodes.map((p) => {
        const n = p.node
        const x = cx(p) - NODE_W / 2
        const y = cy(p) - NODE_H / 2
        if (n.leaf) {
          const c = leafColors(n.value)
          return (
            <g key={p.id}>
              <rect
                x={x}
                y={y}
                width={NODE_W}
                height={NODE_H}
                rx={8}
                fill={c.fill}
                stroke={c.stroke}
                strokeWidth={1.5}
              />
              <text
                x={cx(p)}
                y={cy(p) - 6}
                textAnchor="middle"
                dominantBaseline="central"
                fontSize={17}
                fontWeight={700}
                fill="var(--text)"
              >
                {n.leaf_model ? `model μ ${n.value.toFixed(2)}` : `→ ${n.value.toFixed(2)}`}
              </text>
              <text
                x={cx(p)}
                y={cy(p) + 13}
                textAnchor="middle"
                dominantBaseline="central"
                fontSize={10}
                fill="var(--text-muted)"
              >
                n={n.samples}
              </text>
            </g>
          )
        }
        const tip = n.feature ? featureTooltip?.(n.feature) : undefined
        return (
          <g key={p.id}>
            {tip && <title>{tip}</title>}
            <rect
              x={x}
              y={y}
              width={NODE_W}
              height={NODE_H}
              rx={8}
              fill="var(--surface)"
              stroke="var(--accent)"
              strokeWidth={1.5}
            />
            <text
              x={cx(p)}
              y={cy(p) - 7}
              textAnchor="middle"
              dominantBaseline="central"
              fontSize={13}
              fontWeight={600}
              fill="var(--text)"
            >
              {n.feature}
            </text>
            <text
              x={cx(p)}
              y={cy(p) + 12}
              textAnchor="middle"
              dominantBaseline="central"
              fontSize={12}
              fill="var(--text-muted)"
            >
              ≤ {n.threshold}
            </text>
          </g>
        )
      })}
    </svg>
  )
}
