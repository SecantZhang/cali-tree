import type { NodeProps } from '@xyflow/react'
import { SimpleParamNode } from './SimpleParamNode'
import { SocketHandle, socketTop } from './SocketHandle'
import { SOCKET_COLORS } from './socketTypes'
import type { VeNodeData } from './types'

export function RubricLiteApplyNode({ id, data, selected }: NodeProps) {
  const d = data as VeNodeData
  return (
    <SimpleParamNode
      id={id} data={d} selected={selected}
      title="Rubric-Lite Apply" color="var(--node-calibration)"
      schema={{}}
      staticBody={<div className="rf-node-param">2 cutpoints · 0 model calls</div>}
      sockets={
        <>
          <SocketHandle
            kind="target" id="judge_result" label="judge_result"
            top={socketTop(0, 2)} color={SOCKET_COLORS.judge_result}
          />
          <SocketHandle
            kind="target" id="rubric_calibrator" label="rubric_calibrator"
            top={socketTop(1, 2)} color={SOCKET_COLORS.rubric_calibrator}
          />
          <SocketHandle
            kind="source" id="judge_result" label="judge_result"
            top={socketTop(0, 1)} color={SOCKET_COLORS.judge_result}
          />
        </>
      }
    />
  )
}
