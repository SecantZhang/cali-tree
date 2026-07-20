import type { NodeProps } from '@xyflow/react'
import { NODE_PARAM_SCHEMAS } from './paramSchemas'
import { SimpleParamNode } from './SimpleParamNode'
import { SocketHandle, socketTop } from './SocketHandle'
import { SOCKET_COLORS } from './socketTypes'
import type { VeNodeData } from './types'

export function ClRuleTreeNode({ id, data, selected }: NodeProps) {
  const d = data as VeNodeData
  return (
    <SimpleParamNode
      id={id}
      data={d}
      selected={selected}
      title="Rule/Tree Calibration"
      color="var(--node-calibration)"
      schema={NODE_PARAM_SCHEMAS.cl_rule_tree}
      summaryLine={(p) => `up to ${p.max_questions ?? 5} rules`}
      // 4 target sockets — widen the zone so handles stay separable (see NodeChrome).
      socketZoneHeight={90}
      sockets={
        <>
          <SocketHandle
            kind="target" id="samples" label="samples" top={socketTop(0, 4)}
            color={SOCKET_COLORS.samples}
          />
          <SocketHandle
            kind="target" id="calibration_results" label="calibration_results" top={socketTop(1, 4)}
            color={SOCKET_COLORS.calibration_results}
          />
          <SocketHandle
            kind="target" id="labels" label="labels" top={socketTop(2, 4)}
            color={SOCKET_COLORS.labels}
          />
          <SocketHandle
            kind="target" id="critic_engine" label="critic_engine" top={socketTop(3, 4)}
            color={SOCKET_COLORS.engine_config}
          />
          <SocketHandle
            kind="source" id="judge_rule" label="judge_rule" top={socketTop(0, 1)}
            color={SOCKET_COLORS.judge_rule}
          />
        </>
      }
    />
  )
}
