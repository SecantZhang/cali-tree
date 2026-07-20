import type { NodeProps } from '@xyflow/react'
import { NODE_PARAM_SCHEMAS } from './paramSchemas'
import { SimpleParamNode } from './SimpleParamNode'
import { SocketHandle, socketTop } from './SocketHandle'
import { SOCKET_COLORS } from './socketTypes'
import type { VeNodeData } from './types'

export function CoconutSourceNode({ id, data, selected }: NodeProps) {
  const d = data as VeNodeData
  return (
    <SimpleParamNode
      id={id}
      data={d}
      selected={selected}
      title="Coconut Source"
      color="var(--node-db)"
      schema={NODE_PARAM_SCHEMAS.coconut_source}
      summaryLine={() => 'model: coconut'}
      sockets={
        <SocketHandle
          kind="source" id="raw_dataset" label="raw_dataset" top={socketTop(0, 1)}
          color={SOCKET_COLORS.raw_dataset}
        />
      }
    />
  )
}
