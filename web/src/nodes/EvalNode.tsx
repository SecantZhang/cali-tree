import type { NodeProps } from '@xyflow/react'
import { NODE_PARAM_SCHEMAS } from './paramSchemas'
import { SimpleParamNode } from './SimpleParamNode'
import { SocketHandle, socketTop } from './SocketHandle'
import { SOCKET_COLORS } from './socketTypes'
import type { VeNodeData } from './types'

export function EvalNode({ id, data, selected }: NodeProps) {
  const d = data as VeNodeData
  return (
    <SimpleParamNode
      id={id}
      data={d}
      selected={selected}
      title="Eval"
      color="var(--node-eval)"
      schema={NODE_PARAM_SCHEMAS.eval}
      staticBody={<div className="rf-node-param">human-vs-judge agreement</div>}
      sockets={
        <>
          <SocketHandle
            kind="target" id="judge_result_text" label="judge_result_text" top={socketTop(0, 3)}
            color={SOCKET_COLORS.judge_result}
          />
          <SocketHandle
            kind="target" id="judge_result_video" label="judge_result_video" top={socketTop(1, 3)}
            color={SOCKET_COLORS.judge_result}
          />
          <SocketHandle
            kind="target" id="labels" label="labels" top={socketTop(2, 3)}
            color={SOCKET_COLORS.labels}
          />
          <SocketHandle
            kind="source" id="metrics_report" label="metrics_report" top={socketTop(0, 1)}
            color={SOCKET_COLORS.metrics_report}
          />
        </>
      }
    />
  )
}
