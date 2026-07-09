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
