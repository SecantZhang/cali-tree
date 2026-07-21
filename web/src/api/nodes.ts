import { api } from './client'

export interface NodeTypeOut {
  type: string
  category: string
  subcategory?: string | null
  input_sockets: Record<string, string>
  output_sockets: Record<string, string>
  // Input sockets that accept fan-in (multiple incoming edges). The backend sends this on
  // every /api/nodes entry; it was previously dropped from this type.
  multi_input_sockets: string[]
  param_schema: Record<string, unknown>
}

export function fetchNodeTypes(): Promise<NodeTypeOut[]> {
  return api.get('/api/nodes')
}
