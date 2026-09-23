import type { NodeProps } from '@xyflow/react'
import { NODE_PARAM_SCHEMAS } from './paramSchemas'
import { SimpleParamNode } from './SimpleParamNode'
import { SocketHandle, socketTop } from './SocketHandle'
import { SOCKET_COLORS } from './socketTypes'
import type { VeNodeData } from './types'

export function AreaRubricNode({ id, data, selected }: NodeProps) {
  const d = data as VeNodeData
  return (
    <SimpleParamNode id={id} data={d} selected={selected} title="Area Rubric Spec"
      color="var(--node-vejudge)" schema={NODE_PARAM_SCHEMAS.area_rubric}
      summaryLine={(p) => String(p.rubric || 'transition_smoothness')}
      sockets={<SocketHandle kind="source" id="area_rubric_spec" label="area_rubric_spec"
        top={socketTop(0, 1)} color={SOCKET_COLORS.area_rubric_spec} />}
    />
  )
}
