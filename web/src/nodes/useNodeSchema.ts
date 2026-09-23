import { useQuery } from '@tanstack/react-query'
import { fetchNodeTypes } from '../api/nodes'

// A node's I/O socket schema, sourced from the live backend node-type API (GET /api/nodes)
// rather than the hand-maintained static mirror in socketTypes.ts. Because the backend
// projects this straight from each NodeExecutor's `input_sockets`/`output_sockets`, any new
// node or changed socket shows up here automatically — the generic Inputs/Outputs tabs and
// their schema header reflect backend changes with no frontend edit. socketTypes.ts stays as
// the source for socket colors + synchronous connection validation only.
export interface NodeSchema {
  input: Record<string, string>
  output: Record<string, string>
  multiInput: Set<string>
}

const EMPTY: NodeSchema = { input: {}, output: {}, multiInput: new Set() }

export function useNodeSchema(type: string | undefined): NodeSchema {
  // Same query key NodesTab.tsx uses, so react-query dedupes/caches it — no extra fetch.
  const { data } = useQuery({ queryKey: ['nodeTypes'], queryFn: fetchNodeTypes })
  if (!type || !data) return EMPTY
  const info = data.find((n) => n.type === type)
  if (!info) return EMPTY
  return {
    input: info.input_sockets,
    output: info.output_sockets,
    multiInput: new Set(info.multi_input_sockets ?? []),
  }
}
