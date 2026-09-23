import type { NodeProps } from '@xyflow/react'
import { NODE_PARAM_SCHEMAS } from './paramSchemas'
import { SimpleParamNode } from './SimpleParamNode'
import { SocketHandle, socketTop } from './SocketHandle'
import { SOCKET_COLORS } from './socketTypes'
import type { VeNodeData } from './types'

export function RubricLiteFitNode({ id, data, selected }: NodeProps) {
  const d = data as VeNodeData
  return (
    <SimpleParamNode
      id={id} data={d} selected={selected}
      title="Rubric-Lite Fit" color="var(--node-calibration)"
      schema={NODE_PARAM_SCHEMAS.rubric_lite_fit}
      summaryLine={(params) => `2 cutpoints · ${String(params.selection_objective ?? 'macro_f1')}`}
      socketZoneHeight={80}
      sockets={
        <>
          {['judge_result', 'labels', 'samples'].map((name, index) => (
            <SocketHandle
              key={name} kind="target" id={name} label={name}
              top={socketTop(index, 3)}
              color={
                name === 'judge_result' ? SOCKET_COLORS.judge_result
                  : name === 'labels' ? SOCKET_COLORS.labels
                    : SOCKET_COLORS.samples
              }
            />
          ))}
          <SocketHandle
            kind="source" id="rubric_calibrator" label="rubric_calibrator"
            top={socketTop(0, 2)} color={SOCKET_COLORS.rubric_calibrator}
          />
          <SocketHandle
            kind="source" id="calitree_report" label="calitree_report"
            top={socketTop(1, 2)} color={SOCKET_COLORS.calitree_report}
          />
        </>
      }
    />
  )
}
