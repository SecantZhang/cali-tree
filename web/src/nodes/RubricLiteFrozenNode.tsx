import type { NodeProps } from '@xyflow/react'
import { NODE_PARAM_SCHEMAS } from './paramSchemas'
import { SimpleParamNode } from './SimpleParamNode'
import { SocketHandle, socketTop } from './SocketHandle'
import { SOCKET_COLORS } from './socketTypes'
import type { VeNodeData } from './types'

export function RubricLiteFrozenNode({ id, data, selected }: NodeProps) {
  const d = data as VeNodeData
  return (
    <SimpleParamNode
      id={id} data={d} selected={selected}
      title="Frozen Rubric-Lite" color="var(--node-calibration)"
      schema={NODE_PARAM_SCHEMAS.rubric_lite_frozen}
      summaryLine={() => 'v4 · frozen global cutpoints'}
      sockets={
        <SocketHandle
          kind="source" id="prompt_tree" label="prompt_tree"
          top={socketTop(0, 1)} color={SOCKET_COLORS.prompt_tree}
        />
      }
    />
  )
}
