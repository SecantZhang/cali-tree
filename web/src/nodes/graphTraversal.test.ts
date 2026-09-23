import { describe, expect, it } from 'vitest'
import type { Edge } from '@xyflow/react'
import { ancestorsOf, descendantsOf } from './graphTraversal'

function edge(source: string, target: string): Edge {
  return { id: `${source}->${target}`, source, target }
}

describe('descendantsOf', () => {
  it('returns every transitive downstream node, not just direct children', () => {
    // a -> b -> c, plus a -> d (a sibling branch)
    const edges = [edge('a', 'b'), edge('b', 'c'), edge('a', 'd')]
    expect(descendantsOf(edges, 'a')).toEqual(new Set(['b', 'c', 'd']))
  })

  it('excludes ancestors and unrelated nodes', () => {
    const edges = [edge('a', 'b'), edge('b', 'c')]
    expect(descendantsOf(edges, 'c')).toEqual(new Set())
    expect(descendantsOf(edges, 'b')).toEqual(new Set(['c']))
  })

  it('handles a diamond without infinite looping or duplicate visits', () => {
    // a -> b -> d, a -> c -> d
    const edges = [edge('a', 'b'), edge('a', 'c'), edge('b', 'd'), edge('c', 'd')]
    expect(descendantsOf(edges, 'a')).toEqual(new Set(['b', 'c', 'd']))
  })

  it('returns an empty set for a node with no outgoing edges', () => {
    expect(descendantsOf([edge('a', 'b')], 'b')).toEqual(new Set())
  })
})

describe('ancestorsOf', () => {
  it('returns every transitive predecessor, not just direct parents', () => {
    // a -> b -> c, plus d -> c (a second incoming branch)
    const edges = [edge('a', 'b'), edge('b', 'c'), edge('d', 'c')]
    expect(ancestorsOf(edges, 'c')).toEqual(new Set(['a', 'b', 'd']))
  })

  it('excludes descendants and unrelated nodes', () => {
    const edges = [edge('a', 'b'), edge('b', 'c')]
    expect(ancestorsOf(edges, 'a')).toEqual(new Set())
    expect(ancestorsOf(edges, 'b')).toEqual(new Set(['a']))
  })

  it('handles a diamond without infinite looping', () => {
    const edges = [edge('a', 'b'), edge('a', 'c'), edge('b', 'd'), edge('c', 'd')]
    expect(ancestorsOf(edges, 'd')).toEqual(new Set(['a', 'b', 'c']))
  })
})
