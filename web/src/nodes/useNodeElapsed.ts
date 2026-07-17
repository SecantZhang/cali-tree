import { useEffect, useRef, useState } from 'react'
import { useActiveRunStore } from '../store/activeTab'
import type { NodeStatus } from './types'

// Elapsed run time (ms) for a node's on-chrome badge: while the node is `running`, a live
// value ticked from a client-recorded start (the WS is status-only, so no server time
// arrives mid-run); otherwise the authoritative backend-measured `meta.elapsed_ms` from the
// last completed run. Returns null when the node has never run.
export function useNodeElapsedMs(id: string, status: NodeStatus): number | null {
  const finalMs = useActiveRunStore((s) => {
    const v = (s.lastNodeResults[id]?.meta as Record<string, unknown> | undefined)?.elapsed_ms
    return typeof v === 'number' ? v : null
  })
  const [, setTick] = useState(0)
  const startRef = useRef<number | null>(null)

  useEffect(() => {
    if (status === 'running') {
      if (startRef.current == null) startRef.current = performance.now()
      const iv = setInterval(() => setTick((t) => t + 1), 200)
      return () => clearInterval(iv)
    }
    startRef.current = null
  }, [status])

  if (status === 'running' && startRef.current != null) {
    return performance.now() - startRef.current
  }
  return finalMs
}
