import type { Edge } from '@xyflow/react'
import { describe, expect, it } from 'vitest'
import type { GroupSpec, VeNode } from '../store/graphStore'
import { topologicalLayout } from './topologicalLayout'

function node(id: string, x = 0, y = 0): VeNode {
  return {
    id,
    type: 'judge',
    position: { x, y },
    width: 240,
    height: 120,
    data: { params: {}, status: 'idle' },
  }
}

function edge(source: string, target: string): Edge {
  return { id: `${source}->${target}`, source, target }
}

describe('topologicalLayout', () => {
  it('places dependencies in columns and separates parallel nodes vertically', () => {
    const result = topologicalLayout(
      [node('a'), node('b'), node('c'), node('d')],
      [edge('a', 'c'), edge('b', 'c'), edge('c', 'd')],
      [],
    )
    const positions = Object.fromEntries(result.nodes.map((n) => [n.id, n.position]))
    expect(positions.a.x).toBe(positions.b.x)
    expect(positions.a.y).not.toBe(positions.b.y)
    expect(positions.c.x).toBeGreaterThan(positions.a.x)
    expect(positions.d.x).toBeGreaterThan(positions.c.x)
    expect(result.hasCycle).toBe(false)
  })

  it('uses the longest dependency path for topological depth', () => {
    const result = topologicalLayout(
      [node('root'), node('middle'), node('shortcut'), node('leaf')],
      [
        edge('root', 'middle'), edge('middle', 'leaf'),
        edge('shortcut', 'leaf'),
      ],
      [],
    )
    const x = Object.fromEntries(result.nodes.map((n) => [n.id, n.position.x]))
    expect(x.root).toBe(x.shortcut)
    expect(x.middle).toBeGreaterThan(x.root)
    expect(x.leaf).toBeGreaterThan(x.middle)
  })

  it('keeps prior group members inside a resized group', () => {
    const nodes = [node('inside', 20, 20), node('outside', 800, 800)]
    const groups: GroupSpec[] = [{
      id: 'g', title: 'Inputs', position: { x: 0, y: 0 },
      size: { width: 400, height: 300 },
    }]
    const result = topologicalLayout(nodes, [], groups)
    const inside = result.nodes.find((n) => n.id === 'inside')!
    const group = result.groups[0]
    expect(inside.position.x).toBeGreaterThan(group.position.x)
    expect(inside.position.y).toBeGreaterThan(group.position.y)
    expect(inside.position.x + 240).toBeLessThan(group.position.x + group.size.width)
    expect(inside.position.y + 120).toBeLessThan(group.position.y + group.size.height)
  })

  it('moves cyclic nodes to a visible final column', () => {
    const result = topologicalLayout(
      [node('root'), node('cycle-a'), node('cycle-b')],
      [edge('cycle-a', 'cycle-b'), edge('cycle-b', 'cycle-a')],
      [],
    )
    const positions = Object.fromEntries(result.nodes.map((n) => [n.id, n.position]))
    expect(result.hasCycle).toBe(true)
    expect(positions['cycle-a'].x).toBeGreaterThan(positions.root.x)
    expect(positions['cycle-a'].y).not.toBe(positions['cycle-b'].y)
  })
})
