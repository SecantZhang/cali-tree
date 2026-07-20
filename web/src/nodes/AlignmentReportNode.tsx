import type { NodeProps } from '@xyflow/react'
import { NODE_PARAM_SCHEMAS } from './paramSchemas'
import { SimpleParamNode } from './SimpleParamNode'
import { SocketHandle, socketTop } from './SocketHandle'
import { SOCKET_COLORS } from './socketTypes'
import type { VeNodeData } from './types'

export function AlignmentReportNode({ id, data, selected }: NodeProps) {
  const d = data as VeNodeData
  return (
    <SimpleParamNode
      id={id}
      data={d}
      selected={selected}
      title="Alignment Report"
      color="var(--node-eval)"
      schema={NODE_PARAM_SCHEMAS.alignment_report}
      staticBody={<div className="rf-node-param">SRCC/PLCC/KRCC vs VE-Bench</div>}
      sockets={
        <>
          <SocketHandle
            kind="target" id="metrics_report" label="metrics_report" top={socketTop(0, 1)}
            color={SOCKET_COLORS.metrics_report}
          />
          <SocketHandle
            kind="source" id="comparison" label="comparison" top={socketTop(0, 1)}
            color={SOCKET_COLORS.metrics_report}
          />
        </>
      }
    />
  )
}
