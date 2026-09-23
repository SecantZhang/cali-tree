import type { NodeProps } from '@xyflow/react'
import { NODE_PARAM_SCHEMAS } from './paramSchemas'
import { SimpleParamNode } from './SimpleParamNode'
import { SocketHandle, socketTop } from './SocketHandle'
import { SOCKET_COLORS } from './socketTypes'
import type { VeNodeData } from './types'

export function AreaJudgeNode({ id, data, selected }: NodeProps) {
  const d = data as VeNodeData
  const inputs = [
    ['samples', SOCKET_COLORS.samples],
    ['evidence_bundle', SOCKET_COLORS.evidence_bundle],
    ['engine_config', SOCKET_COLORS.engine_config],
    ['area_rubric_spec', SOCKET_COLORS.area_rubric_spec],
  ] as const
  return (
    <SimpleParamNode id={id} data={d} selected={selected} title="Area Judge"
      color="var(--node-vejudge)" schema={NODE_PARAM_SCHEMAS.area_judge}
      socketZoneHeight={90} summaryLine={() => 'one call per selected unit'}
      sockets={<>
        {inputs.map(([name, color], index) => <SocketHandle key={name} kind="target"
          id={name} label={name} top={socketTop(index, inputs.length)} color={color} />)}
        <SocketHandle kind="source" id="area_judge_result" label="area_judge_result"
          top={socketTop(0, 1)} color={SOCKET_COLORS.area_judge_result} />
      </>}
    />
  )
}
