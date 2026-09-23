import type { NodeProps } from '@xyflow/react'
import { NODE_PARAM_SCHEMAS } from './paramSchemas'
import { SimpleParamNode } from './SimpleParamNode'
import { SocketHandle, socketTop } from './SocketHandle'
import { SOCKET_COLORS } from './socketTypes'
import type { VeNodeData } from './types'

export function ClRuleEvalNode({ id, data, selected }: NodeProps) {
  const d = data as VeNodeData
  return (
    <SimpleParamNode
      id={id}
      data={d}
      selected={selected}
      title="Rule Comparison"
      color="var(--node-eval)"
      schema={NODE_PARAM_SCHEMAS.cl_rule_eval}
      staticBody={<div className="rf-node-param">rules vs bias, held-out (LOO)</div>}
      sockets={
        <>
          <SocketHandle
            kind="target" id="judge_rule" label="judge_rule" top={socketTop(0, 1)}
            color={SOCKET_COLORS.judge_rule}
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
