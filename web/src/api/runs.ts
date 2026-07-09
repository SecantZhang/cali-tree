import type { GraphSpecJSON } from '../store/graphStore'
import { api } from './client'

export interface NodeResultOut {
  status: string
  error: string | null
  meta: Record<string, unknown>
  outputs: Record<string, unknown>
}

export interface RunStatusOut {
  run_id: string
  status: string
  error: string | null
  node_results: Record<string, NodeResultOut>
  // This run's actual execution order/scope, once known (empty while still running, or on
  // a structural pre-execution error) — the REST-response mirror of the `run_order` WS
  // event, for a run that finishes before the websocket even connects (common for a tiny
  // or dry run) to still be able to populate the order badge (see useRunSocket.ts).
  order: string[]
}

// Backs the per-node Run (▶, "ancestors": this node's full ancestor chain + itself, from
// scratch) and Re-run (↻, "self_only": just this node, reusing seedRunId's already-computed
// outputs for everything upstream) buttons — see NodeChrome.tsx/SimpleParamNode.tsx. The
// global Run button (RunControls.tsx) omits all three, preserving today's whole-graph run.
export interface ScopedRunOptions {
  targetNodeId: string
  runMode: 'ancestors' | 'self_only'
  seedRunId?: string
}

export function startRun(
  graph: GraphSpecJSON, dryRun: boolean, allowLive: boolean, workflowName?: string | null,
  scope?: ScopedRunOptions,
): Promise<RunStatusOut> {
  return api.post('/api/runs', {
    graph, dry_run: dryRun, allow_live: allowLive, workflow_name: workflowName || undefined,
    target_node_id: scope?.targetNodeId,
    run_mode: scope?.runMode,
    seed_run_id: scope?.seedRunId,
  })
}

export function resumeRun(resumeFrom: string): Promise<RunStatusOut> {
  return api.post('/api/runs', { resume_from: resumeFrom })
}

export function getRun(runId: string): Promise<RunStatusOut> {
  return api.get(`/api/runs/${encodeURIComponent(runId)}`)
}

export function stopRun(runId: string): Promise<RunStatusOut> {
  return api.post(`/api/runs/${encodeURIComponent(runId)}/stop`)
}

export function listRuns(): Promise<string[]> {
  return api.get('/api/runs')
}
