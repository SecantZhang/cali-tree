import type { NodeProps } from '@xyflow/react'
import { NODE_PARAM_SCHEMAS } from './paramSchemas'
import { SimpleParamNode } from './SimpleParamNode'
import { SocketHandle, socketTop } from './SocketHandle'
import { SOCKET_COLORS } from './socketTypes'
import type { VeNodeData } from './types'

export function EvalTextNode({ id, data, selected }: NodeProps) {
  const d = data as VeNodeData
  return (
    <SimpleParamNode
      id={id}
      data={d}
      selected={selected}
      title="Eval Text"
      color="var(--node-eval)"
      schema={NODE_PARAM_SCHEMAS.eval_text}
      staticBody={<div className="rf-node-param">human-vs-judge agreement (text)</div>}
      sockets={
        <>
          <SocketHandle
            kind="target" id="judge_result" label="judge_result" top={socketTop(0, 2)}
            color={SOCKET_COLORS.judge_result}
          />
          <SocketHandle
            kind="target" id="labels" label="labels" top={socketTop(1, 2)}
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
