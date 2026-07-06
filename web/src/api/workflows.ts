import type { GraphSpecJSON } from '../store/graphStore'
import { api } from './client'

export interface WorkflowOut {
  name: string
  graph: GraphSpecJSON
  created_at: string
  updated_at: string
}

export function listWorkflows(): Promise<string[]> {
  return api.get('/api/workflows')
}

export function getWorkflow(name: string): Promise<WorkflowOut> {
  return api.get(`/api/workflows/${encodeURIComponent(name)}`)
}

export function saveWorkflow(name: string, graph: GraphSpecJSON): Promise<WorkflowOut> {
  return api.post('/api/workflows', { name, graph })
}

export function deleteWorkflow(name: string): Promise<{ deleted: string }> {
  return api.delete(`/api/workflows/${encodeURIComponent(name)}`)
}
