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
}

export function startRun(
  graph: GraphSpecJSON, dryRun: boolean, allowLive: boolean, workflowName?: string | null,
): Promise<RunStatusOut> {
  return api.post('/api/runs', {
    graph, dry_run: dryRun, allow_live: allowLive, workflow_name: workflowName || undefined,
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
