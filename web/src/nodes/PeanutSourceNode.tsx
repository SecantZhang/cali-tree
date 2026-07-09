import type { NodeProps } from '@xyflow/react'
import { NODE_PARAM_SCHEMAS } from './paramSchemas'
import { SimpleParamNode } from './SimpleParamNode'
import { SocketHandle, socketTop } from './SocketHandle'
import { SOCKET_COLORS } from './socketTypes'
import type { VeNodeData } from './types'

export function PeanutSourceNode({ id, data, selected }: NodeProps) {
  const d = data as VeNodeData
  return (
    <SimpleParamNode
      id={id}
      data={d}
      selected={selected}
      title="Peanut Source"
      color="var(--node-db)"
      schema={NODE_PARAM_SCHEMAS.peanut_source}
      summaryLine={(p) => `model: ${p.model ?? 'peanut'}`}
      sockets={
        <SocketHandle
          kind="source" id="raw_dataset" label="raw_dataset" top={socketTop(0, 1)}
          color={SOCKET_COLORS.raw_dataset}
        />
      }
    />
  )
}
