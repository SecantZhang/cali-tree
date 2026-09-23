import type { Edge } from '@xyflow/react'

// Pure forward BFS over the current canvas's own edges — used the moment a per-node Run/
// Re-run is *launched* (not on completion) to mark every current descendant of the
// executed node `stale` (see runStore.ts's `staleNodeIds` and NodeChrome.tsx's badge),
// since an ancestor's fresh output can invalidate all of them immediately, well before the
// scoped run itself finishes.
export function descendantsOf(edges: Edge[], id: string): Set<string> {
  const outgoing = new Map<string, string[]>()
  for (const e of edges) {
    const targets = outgoing.get(e.source) ?? []
    targets.push(e.target)
    outgoing.set(e.source, targets)
  }

  const descendants = new Set<string>()
  const frontier = [id]
  while (frontier.length) {
    const nid = frontier.pop()!
    for (const next of outgoing.get(nid) ?? []) {
      if (!descendants.has(next)) {
        descendants.add(next)
        frontier.push(next)
      }
    }
  }
  return descendants
}

// Mirror of `descendantsOf` over *incoming* edges — every transitive predecessor of `id`.
// Used to lock a node's whole upstream chain (locking a node locks all its predecessors).
export function ancestorsOf(edges: Edge[], id: string): Set<string> {
  const incoming = new Map<string, string[]>()
  for (const e of edges) {
    const sources = incoming.get(e.target) ?? []
    sources.push(e.source)
    incoming.set(e.target, sources)
  }

  const ancestors = new Set<string>()
  const frontier = [id]
  while (frontier.length) {
    const nid = frontier.pop()!
    for (const prev of incoming.get(nid) ?? []) {
      if (!ancestors.has(prev)) {
        ancestors.add(prev)
        frontier.push(prev)
      }
    }
  }
  return ancestors
}
