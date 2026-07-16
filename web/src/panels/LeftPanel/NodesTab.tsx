import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { fetchNodeTypes, type NodeTypeOut } from '../../api/nodes'
import {
  CATEGORY_COLORS,
  CATEGORY_LABELS,
  CATEGORY_ORDER,
  SUBCATEGORY_LABELS,
  SUBCATEGORY_ORDER,
} from '../../nodes/categoryColors'
import { activeGraphStore, useActiveGraphStore } from '../../store/activeTab'

const SUB_NONE = '__none__'

// Order a category's subcategory keys: known ones first (SUBCATEGORY_ORDER), then any
// others alphabetically, and the "no subcategory" bucket last.
function orderedSubKeys(keys: string[]): string[] {
  const known = SUBCATEGORY_ORDER.filter((k) => keys.includes(k))
  const rest = keys.filter((k) => k !== SUB_NONE && !known.includes(k)).sort()
  const none = keys.includes(SUB_NONE) ? [SUB_NONE] : []
  return [...known, ...rest, ...none]
}

export function NodesTab() {
  const { data, isLoading, isError } = useQuery({
    queryKey: ['nodeTypes'],
    queryFn: fetchNodeTypes,
  })
  const addNode = useActiveGraphStore((s) => s.addNode)
  // Folder-style grouping by category (Data Source/Dataset, Preprocessing, Judge ->
  // Text/Video, Eval) — collapsed state defaults to all-expanded, same as a flat list.
  const [collapsedCategories, setCollapsedCategories] = useState<Set<string>>(new Set())

  const handleAdd = (type: string) => {
    const n = activeGraphStore().getState().nodes.length
    // Nodes are ~200px wide but can grow with content; sockets now live in a fixed zone
    // right below the header (see NodeChrome.tsx's A4 layout), so a too-tight horizontal
    // gap between adjacent nodes can visually overlap right where a socket sits, not just
    // somewhere in the middle of the param body — give real breathing room, not just a
    // few px past the min-width.
    addNode(type, { x: 80 + (n % 5) * 280, y: 80 + Math.floor(n / 5) * 220 })
  }

  // Reused for both category keys and composite `category::subcategory` keys.
  const toggleCategory = (key: string) => {
    setCollapsedCategories((prev) => {
      const next = new Set(prev)
      if (next.has(key)) next.delete(key)
      else next.add(key)
      return next
    })
  }

  const renderItem = (n: NodeTypeOut) => (
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
  )

  // A category renders flat unless some of its nodes declare a subcategory, in which case
  // it splits into collapsible sub-folders (keyed `category::sub`) with any un-subcategorized
  // nodes falling into a trailing bucket.
  const renderCategoryBody = (category: string, items: NodeTypeOut[]) => {
    const bySub = new Map<string, NodeTypeOut[]>()
    for (const n of items) {
      const key = n.subcategory || SUB_NONE
      const list = bySub.get(key) ?? []
      list.push(n)
      bySub.set(key, list)
    }
    if (bySub.size === 1 && bySub.has(SUB_NONE)) return items.map(renderItem)

    return orderedSubKeys([...bySub.keys()]).map((sub) => {
      const subItems = bySub.get(sub) ?? []
      const subKey = `${category}::${sub}`
      const subCollapsed = collapsedCategories.has(subKey)
      return (
        <div key={subKey} className="node-palette-subcategory">
          {sub !== SUB_NONE && (
            <button
              className="node-palette-subcategory-header"
              onClick={() => toggleCategory(subKey)}
              aria-expanded={!subCollapsed}
            >
              <span className={`category-chevron${subCollapsed ? ' collapsed' : ''}`}>▾</span>
              {SUBCATEGORY_LABELS[sub] ?? sub}
            </button>
          )}
          {!subCollapsed && subItems.map(renderItem)}
        </div>
      )
    })
  }

  if (isLoading) return <p className="empty-hint">Loading node palette…</p>
  if (isError || !data) {
    return <p className="empty-hint">Could not reach the backend. Is vejudge-interface running?</p>
  }

  const byCategory = new Map<string, NodeTypeOut[]>()
  for (const n of data) {
    const list = byCategory.get(n.category) ?? []
    list.push(n)
    byCategory.set(n.category, list)
  }
  const orderedCategories = [
    ...CATEGORY_ORDER.filter((c) => byCategory.has(c)),
    ...[...byCategory.keys()].filter((c) => !CATEGORY_ORDER.includes(c)).sort(),
  ]

  return (
    <div>
      {orderedCategories.map((category) => {
        const items = byCategory.get(category) ?? []
        const collapsed = collapsedCategories.has(category)
        return (
          <div key={category} className="node-palette-category">
            <button
              className="node-palette-category-header"
              onClick={() => toggleCategory(category)}
              aria-expanded={!collapsed}
            >
              <span className={`category-chevron${collapsed ? ' collapsed' : ''}`}>▾</span>
              {CATEGORY_LABELS[category] ?? category}
            </button>
            {!collapsed && renderCategoryBody(category, items)}
          </div>
        )
      })}
    </div>
  )
}
