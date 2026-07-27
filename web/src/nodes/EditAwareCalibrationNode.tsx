import type { NodeProps } from '@xyflow/react'
import { NODE_PARAM_SCHEMAS } from './paramSchemas'
import { SimpleParamNode } from './SimpleParamNode'
import { SocketHandle, socketTop } from './SocketHandle'
import { SOCKET_COLORS } from './socketTypes'
import type { VeNodeData } from './types'

export function EditAwareCalibrationNode({ id, data, selected }: NodeProps) {
  const d = data as VeNodeData
  const inputs = [
    ['samples', SOCKET_COLORS.samples],
    ['judge_result', SOCKET_COLORS.judge_result],
    ['labels', SOCKET_COLORS.labels],
    ['decomposition_features', SOCKET_COLORS.decomposition_features],
    ['unit_labels', SOCKET_COLORS.unit_labels],
  ] as const
  const outputs = [
    ['judge_result', SOCKET_COLORS.judge_result],
    ['judge_rule', SOCKET_COLORS.judge_rule],
    ['active_labeling_report', SOCKET_COLORS.active_labeling_report],
  ] as const
  return (
    <SimpleParamNode id={id} data={d} selected={selected} title="Edit-Aware Calibration"
      color="var(--node-calibration)" schema={NODE_PARAM_SCHEMAS.edit_aware_calibration}
      socketZoneHeight={110} summaryLine={(p) => `${p.bootstrap_repeats ?? 1000} bootstraps`}
      sockets={<>
        {inputs.map(([name, color], index) => <SocketHandle key={name} kind="target"
          id={name} label={name} top={socketTop(index, inputs.length)} color={color} />)}
        {outputs.map(([name, color], index) => <SocketHandle key={name} kind="source"
          id={name} label={name} top={socketTop(index, outputs.length)} color={color} />)}
      </>}
    />
  )
}
