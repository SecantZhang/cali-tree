import type { NodeProps } from '@xyflow/react'
import { NODE_PARAM_SCHEMAS } from './paramSchemas'
import { SimpleParamNode } from './SimpleParamNode'
import { SocketHandle, socketTop } from './SocketHandle'
import { SOCKET_COLORS } from './socketTypes'
import type { VeNodeData } from './types'

export function ClAdversarialNode({ id, data, selected }: NodeProps) {
  const d = data as VeNodeData
  return (
    <SimpleParamNode
      id={id}
      data={d}
      selected={selected}
      title="Adversarial Calibration"
      color="var(--node-calibration)"
      schema={NODE_PARAM_SCHEMAS.cl_adversarial}
      summaryLine={(p) => `${p.metric_id ?? 'M4'} · max ${p.max_rounds ?? 4} rounds`}
      sockets={
        <>
          <SocketHandle
            kind="target" id="samples" label="samples" top={socketTop(0, 4)}
            color={SOCKET_COLORS.samples}
          />
          <SocketHandle
            kind="target" id="labels" label="labels" top={socketTop(1, 4)}
            color={SOCKET_COLORS.labels}
          />
          <SocketHandle
            kind="target" id="judge_engine" label="judge_engine" top={socketTop(2, 4)}
            color={SOCKET_COLORS.engine_config}
          />
          <SocketHandle
            kind="target" id="human_engine" label="human_engine" top={socketTop(3, 4)}
            color={SOCKET_COLORS.engine_config}
          />
          <SocketHandle
            kind="source" id="calibration_results" label="calibration_results" top={socketTop(0, 1)}
            color={SOCKET_COLORS.calibration_results}
          />
        </>
      }
    />
  )
}
