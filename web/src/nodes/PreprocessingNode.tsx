import type { NodeProps } from '@xyflow/react'
import { NODE_PARAM_SCHEMAS } from './paramSchemas'
import { SimpleParamNode } from './SimpleParamNode'
import { SocketHandle, socketTop } from './SocketHandle'
import { SOCKET_COLORS } from './socketTypes'
import type { VeNodeData } from './types'

export function PreprocessingNode({ id, data, selected }: NodeProps) {
  const d = data as VeNodeData
  return (
    <SimpleParamNode
      id={id}
      data={d}
      selected={selected}
      title="Preprocessing"
      color="var(--node-preprocessing)"
      schema={NODE_PARAM_SCHEMAS.preprocessing}
      summaryLine={(p) => `strategy: ${p.input_strategy ?? 'A'}`}
      sockets={
        <>
          <SocketHandle
            kind="target" id="dataset" label="dataset" top={socketTop(0, 1)}
            color={SOCKET_COLORS.dataset}
          />
          <SocketHandle
            kind="source" id="dataset" label="dataset" top={socketTop(0, 1)}
            color={SOCKET_COLORS.dataset}
          />
        </>
      }
    />
  )
}
