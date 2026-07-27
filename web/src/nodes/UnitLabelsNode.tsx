import type { NodeProps } from '@xyflow/react'
import { NODE_PARAM_SCHEMAS } from './paramSchemas'
import { SimpleParamNode } from './SimpleParamNode'
import { SocketHandle, socketTop } from './SocketHandle'
import { SOCKET_COLORS } from './socketTypes'
import type { VeNodeData } from './types'

export function UnitLabelsNode({ id, data, selected }: NodeProps) {
  const d = data as VeNodeData
  return (
    <SimpleParamNode id={id} data={d} selected={selected} title="Human Unit Labels"
      color="var(--node-db)" schema={NODE_PARAM_SCHEMAS.unit_labels}
      summaryLine={(p) => String(p.path || 'no file')}
      sockets={<SocketHandle kind="source" id="unit_labels" label="unit_labels"
        top={socketTop(0, 1)} color={SOCKET_COLORS.unit_labels} />}
    />
  )
}
