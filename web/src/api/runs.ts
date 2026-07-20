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

// Locked nodes are seeded from a prior run (`seedRunId`) and skipped — layered on top of any
// scope. Passed on every run (global or scoped) when the graph has locked nodes.
export interface LockOptions {
  nodeIds: string[]
  seedRunId: string | null
}

export function startRun(
  graph: GraphSpecJSON, dryRun: boolean, allowLive: boolean, workflowName?: string | null,
  scope?: ScopedRunOptions, lock?: LockOptions,
): Promise<RunStatusOut> {
  return api.post('/api/runs', {
    graph, dry_run: dryRun, allow_live: allowLive, workflow_name: workflowName || undefined,
    target_node_id: scope?.targetNodeId,
    run_mode: scope?.runMode,
    seed_run_id: scope?.seedRunId ?? lock?.seedRunId ?? undefined,
    locked_node_ids: lock?.nodeIds?.length ? lock.nodeIds : undefined,
  })
}

export function resumeRun(resumeFrom: string): Promise<RunStatusOut> {
  return api.post('/api/runs', { resume_from: resumeFrom })
}

export function getRun(runId: string): Promise<RunStatusOut> {
  return api.get(`/api/runs/${encodeURIComponent(runId)}`)
}

// Past runs discovered on disk under logs/exps (the Runs browser). Survives restarts —
// unlike the in-memory-only `GET /api/runs` id list.
export interface DiskRunSummary {
  run_id: string
  workflow_name: string | null
  status: string
  finished_at: string | null
  n_checkpointed: number
  n_nodes: number | null
}

export function listDiskRuns(): Promise<DiskRunSummary[]> {
  return api.get('/api/runs/disk')
}

// The saved graph for a past run (workflow_graph.json shape — no canvas layout, so
// positions auto-grid on load). Loadable into a tab via loadGraph/openRunTab.
export function getRunGraph(runId: string): Promise<GraphSpecJSON> {
  return api.get(`/api/runs/${encodeURIComponent(runId)}/graph`)
}

export function stopRun(runId: string): Promise<RunStatusOut> {
  return api.post(`/api/runs/${encodeURIComponent(runId)}/stop`)
}

export function listRuns(): Promise<string[]> {
  return api.get('/api/runs')
}
