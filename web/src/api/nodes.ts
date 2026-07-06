import { api } from './client'

export interface NodeTypeOut {
  type: string
  category: string
  input_sockets: Record<string, string>
  output_sockets: Record<string, string>
  param_schema: Record<string, unknown>
}

export function fetchNodeTypes(): Promise<NodeTypeOut[]> {
  return api.get('/api/nodes')
}
