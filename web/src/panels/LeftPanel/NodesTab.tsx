import { useQuery } from '@tanstack/react-query'
import { fetchNodeTypes } from '../../api/nodes'
import { CATEGORY_COLORS } from '../../nodes/categoryColors'
import { useGraphStore } from '../../store/graphStore'

export function NodesTab() {
  const { data, isLoading, isError } = useQuery({
    queryKey: ['nodeTypes'],
    queryFn: fetchNodeTypes,
  })
  const addNode = useGraphStore((s) => s.addNode)

  const handleAdd = (type: string) => {
    const n = useGraphStore.getState().nodes.length
    addNode(type, { x: 80 + (n % 5) * 220, y: 80 + Math.floor(n / 5) * 160 })
  }

  if (isLoading) return <p className="empty-hint">Loading node palette…</p>
  if (isError || !data) {
    return <p className="empty-hint">Could not reach the backend. Is vejudge-interface running?</p>
  }

  return (
    <div>
      {data.map((n) => (
        <div
          key={n.type}
          className="node-palette-item"
          onClick={() => handleAdd(n.type)}
          role="button"
          tabIndex={0}
          onKeyDown={(e) => {
            if (e.key === 'Enter' || e.key === ' ') handleAdd(n.type)
          }}
        >
          <span className="swatch" style={{ background: CATEGORY_COLORS[n.category] }} />
          {n.type}
        </div>
      ))}
    </div>
  )
}
