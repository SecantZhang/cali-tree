import type { Node } from '@xyflow/react'
import type { GroupSpec } from '../store/graphStore'

interface Rect {
  x: number
  y: number
  width: number
  height: number
}

function rectsIntersect(a: Rect, b: Rect): boolean {
  return (
    a.x < b.x + b.width &&
    a.x + a.width > b.x &&
    a.y < b.y + b.height &&
    a.y + a.height > b.y
  )
}

function nodeRect(n: Node): Rect {
  const width = n.width ?? n.measured?.width ?? 0
  const height = n.height ?? n.measured?.height ?? 0
  return { x: n.position.x, y: n.position.y, width, height }
}

// Ids of nodes whose bounding box touches (overlaps) the group's rect — ComfyUI-style
// membership. Snapshotted at group-drag-start so those nodes move rigidly with the group.
export function nodesInGroup(group: GroupSpec, nodes: Node[]): string[] {
  const groupRect: Rect = {
    x: group.position.x,
    y: group.position.y,
    width: group.size.width,
    height: group.size.height,
  }
  return nodes.filter((n) => rectsIntersect(nodeRect(n), groupRect)).map((n) => n.id)
}
