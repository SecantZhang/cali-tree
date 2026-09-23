import type { Node } from '@xyflow/react'
import { describe, expect, it } from 'vitest'
import type { GroupSpec } from '../store/graphStore'
import { nodesInGroup } from './geometry'

const group: GroupSpec = {
  id: 'g1',
  title: 'G',
  position: { x: 100, y: 100 },
  size: { width: 200, height: 200 }, // covers x:100..300, y:100..300
}

function node(id: string, x: number, y: number, w = 80, h = 60): Node {
  return { id, type: 'judge', position: { x, y }, width: w, height: h, data: {} }
}

describe('nodesInGroup', () => {
  it('includes nodes whose bounding box overlaps the group rect', () => {
    const inside = node('inside', 150, 150) // fully inside
    const overlapping = node('overlap', 80, 80) // straddles the top-left corner
    const outside = node('outside', 400, 400) // well clear
    const ids = nodesInGroup(group, [inside, overlapping, outside])
    expect(new Set(ids)).toEqual(new Set(['inside', 'overlap']))
  })

  it('excludes a node that merely touches an edge without overlapping (adjacency, not overlap)', () => {
    // Right edge at x=300; a node starting exactly at x=300 shares the boundary but has no
    // positive-area overlap, so it's not a member.
    const flush = node('flush', 300, 150)
    expect(nodesInGroup(group, [flush])).toEqual([])
  })

  it('falls back to measured size when width/height are unset', () => {
    const measured: Node = {
      id: 'm', type: 'judge', position: { x: 150, y: 150 }, data: {},
      measured: { width: 40, height: 40 },
    }
    expect(nodesInGroup(group, [measured])).toEqual(['m'])
  })
})
