import type { NodeProps } from '@xyflow/react'
import { NODE_PARAM_SCHEMAS } from './paramSchemas'
import { SimpleParamNode } from './SimpleParamNode'
import { SocketHandle, socketTop } from './SocketHandle'
import { SOCKET_COLORS } from './socketTypes'
import type { VeNodeData } from './types'

export function EditDecompositionNode({ id, data, selected }: NodeProps) {
  const d = data as VeNodeData
  return (
    <SimpleParamNode id={id} data={d} selected={selected} title="Edit Decomposition"
      color="var(--node-preprocessing)" schema={NODE_PARAM_SCHEMAS.edit_decomposition}
      summaryLine={(p) => `${p.boundary_context_seconds ?? 2}s boundary context`}
      sockets={<>
        <SocketHandle kind="target" id="samples" label="samples" top={socketTop(0, 1)}
          color={SOCKET_COLORS.samples} />
        <SocketHandle kind="source" id="evidence_bundle" label="evidence_bundle"
          top={socketTop(0, 1)} color={SOCKET_COLORS.evidence_bundle} />
      </>}
    />
  )
}
