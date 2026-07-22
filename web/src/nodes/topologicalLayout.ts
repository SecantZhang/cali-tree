import type { Edge } from '@xyflow/react'
import type { GroupSpec, VeNode } from '../store/graphStore'

const ORIGIN_X = 80
const ORIGIN_Y = 80
const HORIZONTAL_GAP = 180
const VERTICAL_GAP = 72
const DEFAULT_WIDTH = 280
const DEFAULT_HEIGHT = 180
const GROUP_PADDING = 32

function dimensions(node: VeNode): { width: number; height: number } {
  return {
    width: node.width ?? node.measured?.width ?? DEFAULT_WIDTH,
    height: node.height ?? node.measured?.height ?? (node.data.collapsed ? 64 : DEFAULT_HEIGHT),
  }
}

function intersectsGroup(node: VeNode, group: GroupSpec): boolean {
  const { width, height } = dimensions(node)
  return (
    node.position.x < group.position.x + group.size.width
    && node.position.x + width > group.position.x
    && node.position.y < group.position.y + group.size.height
    && node.position.y + height > group.position.y
  )
}

export interface TopologicalLayoutResult {
  nodes: VeNode[]
  groups: GroupSpec[]
  hasCycle: boolean
}

/** Arrange a graph left-to-right by longest-path topological depth. */
export function topologicalLayout(
  nodes: VeNode[], edges: Edge[], groups: GroupSpec[],
): TopologicalLayoutResult {
  if (!nodes.length) return { nodes, groups, hasCycle: false }

  const index = new Map(nodes.map((node, order) => [node.id, order]))
  const ids = new Set(index.keys())
  const outgoing = new Map(nodes.map((node) => [node.id, [] as string[]]))
  const indegree = new Map(nodes.map((node) => [node.id, 0]))
  const depth = new Map(nodes.map((node) => [node.id, 0]))
  for (const edge of edges) {
    if (!ids.has(edge.source) || !ids.has(edge.target)) continue
    outgoing.get(edge.source)!.push(edge.target)
    indegree.set(edge.target, indegree.get(edge.target)! + 1)
  }

  const queue = nodes.filter((node) => indegree.get(node.id) === 0).map((node) => node.id)
  const processed = new Set<string>()
  while (queue.length) {
    queue.sort((a, b) => index.get(a)! - index.get(b)!)
    const source = queue.shift()!
    processed.add(source)
    for (const target of outgoing.get(source) ?? []) {
      depth.set(target, Math.max(depth.get(target)!, depth.get(source)! + 1))
      const remaining = indegree.get(target)! - 1
      indegree.set(target, remaining)
      if (remaining === 0) queue.push(target)
    }
  }

  // A cycle has no topological order. Keep every cycle member visible in one final column
  // instead of overlapping it with roots; valid workflow DAGs never take this path.
  const hasCycle = processed.size !== nodes.length
  if (hasCycle) {
    const finalDepth = Math.max(0, ...depth.values()) + 1
    for (const node of nodes) {
      if (!processed.has(node.id)) depth.set(node.id, finalDepth)
    }
  }

  const layers = new Map<number, VeNode[]>()
  for (const node of nodes) {
    const layer = depth.get(node.id) ?? 0
    layers.set(layer, [...(layers.get(layer) ?? []), node])
  }
  const layerNumbers = [...layers.keys()].sort((a, b) => a - b)
  const columnWidths = new Map(
    layerNumbers.map((layer) => [
      layer,
      Math.max(...layers.get(layer)!.map((node) => dimensions(node).width)),
    ]),
  )
  const columnX = new Map<number, number>()
  let nextX = ORIGIN_X
  for (const layer of layerNumbers) {
    columnX.set(layer, nextX)
    nextX += columnWidths.get(layer)! + HORIZONTAL_GAP
  }

  const layerHeights = new Map<number, number>()
  for (const layer of layerNumbers) {
    const members = layers.get(layer)!
    members.sort((a, b) => a.position.y - b.position.y || index.get(a.id)! - index.get(b.id)!)
    layerHeights.set(
      layer,
      members.reduce((total, node) => total + dimensions(node).height, 0)
      + VERTICAL_GAP * Math.max(0, members.length - 1),
    )
  }
  const tallestLayer = Math.max(...layerHeights.values())
  const positions = new Map<string, { x: number; y: number }>()
  for (const layer of layerNumbers) {
    let nextY = ORIGIN_Y + (tallestLayer - layerHeights.get(layer)!) / 2
    for (const node of layers.get(layer)!) {
      positions.set(node.id, { x: columnX.get(layer)!, y: nextY })
      nextY += dimensions(node).height + VERTICAL_GAP
    }
  }
  const laidOutNodes = nodes.map((node) => ({ ...node, position: positions.get(node.id)! }))

  // Snapshot membership from the pre-layout rectangles, then resize each group around the
  // same members in their new positions. Empty groups remain untouched.
  const laidOutGroups = groups.map((group) => {
    const memberIds = new Set(nodes.filter((node) => intersectsGroup(node, group)).map((n) => n.id))
    const members = laidOutNodes.filter((node) => memberIds.has(node.id))
    if (!members.length) return group
    const minX = Math.min(...members.map((node) => node.position.x))
    const minY = Math.min(...members.map((node) => node.position.y))
    const maxX = Math.max(...members.map((node) => node.position.x + dimensions(node).width))
    const maxY = Math.max(...members.map((node) => node.position.y + dimensions(node).height))
    return {
      ...group,
      position: { x: minX - GROUP_PADDING, y: minY - GROUP_PADDING },
      size: {
        width: maxX - minX + GROUP_PADDING * 2,
        height: maxY - minY + GROUP_PADDING * 2,
      },
    }
  })
  return { nodes: laidOutNodes, groups: laidOutGroups, hasCycle }
}
