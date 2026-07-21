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
      summaryLine={(p) => `max ${p.max_rounds ?? 4} rounds`}
      // 6 target sockets — the default 44px zone (fine for ≤3) packs handles too close
      // together to reliably tell apart (see NodeChrome's socketZoneHeight doc).
      socketZoneHeight={120}
      sockets={
        <>
          <SocketHandle
            kind="target" id="samples" label="samples" top={socketTop(0, 6)}
            color={SOCKET_COLORS.samples}
          />
          <SocketHandle
            kind="target" id="judge_result" label="judge_result" top={socketTop(1, 6)}
            color={SOCKET_COLORS.judge_result}
          />
          <SocketHandle
            kind="target" id="labels" label="labels" top={socketTop(2, 6)}
            color={SOCKET_COLORS.labels}
          />
          <SocketHandle
            kind="target" id="judge_engine" label="judge_engine" top={socketTop(3, 6)}
            color={SOCKET_COLORS.engine_config}
          />
          <SocketHandle
            kind="target" id="human_engine" label="human_engine" top={socketTop(4, 6)}
            color={SOCKET_COLORS.engine_config}
          />
          <SocketHandle
            kind="target" id="summarizer_engine" label="summarizer_engine" top={socketTop(5, 6)}
            color={SOCKET_COLORS.engine_config}
          />
          <SocketHandle
            kind="source" id="calibration_results" label="calibration_results" top={socketTop(0, 2)}
            color={SOCKET_COLORS.calibration_results}
          />
          <SocketHandle
            kind="source" id="general_calibration" label="general_calibration" top={socketTop(1, 2)}
            color={SOCKET_COLORS.general_calibration}
          />
        </>
      }
    />
  )
}
