import type { NodeProps } from '@xyflow/react'
import { NODE_PARAM_SCHEMAS } from './paramSchemas'
import { SimpleParamNode } from './SimpleParamNode'
import { SocketHandle, socketTop } from './SocketHandle'
import { SOCKET_COLORS } from './socketTypes'
import type { VeNodeData } from './types'

export function LMEngineNode({ id, data, selected }: NodeProps) {
  const d = data as VeNodeData
  return (
    <SimpleParamNode
      id={id}
      data={d}
      selected={selected}
      title="LM Engine"
      color="var(--node-vejudge)"
      schema={NODE_PARAM_SCHEMAS.lm_engine}
      summaryLine={(p) => `engine: ${p.engine_kind ?? 'gpt'}`}
      sockets={
        <SocketHandle
          kind="source" id="engine_config" label="engine_config" top={socketTop(0, 1)}
          color={SOCKET_COLORS.engine_config}
        />
      }
    />
  )
}
