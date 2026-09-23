import type { NodeProps } from '@xyflow/react'
import { NODE_PARAM_SCHEMAS } from './paramSchemas'
import { SimpleParamNode } from './SimpleParamNode'
import { SocketHandle, socketTop } from './SocketHandle'
import { SOCKET_COLORS } from './socketTypes'
import type { VeNodeData } from './types'

export function AreaAggregationNode({ id, data, selected }: NodeProps) {
  const d = data as VeNodeData
  return (
    <SimpleParamNode id={id} data={d} selected={selected} title="Area Aggregation"
      color="var(--node-vejudge)" schema={NODE_PARAM_SCHEMAS.area_aggregation}
      staticBody={<div className="rf-node-param">weighted aggregate + severe cap</div>}
      sockets={<>
        <SocketHandle kind="target" id="area_judge_result" label="area_judge_result"
          top={socketTop(0, 2)} color={SOCKET_COLORS.area_judge_result} />
        <SocketHandle kind="target" id="unit_labels" label="unit_labels"
          top={socketTop(1, 2)} color={SOCKET_COLORS.unit_labels} />
        <SocketHandle kind="source" id="judge_result" label="judge_result"
          top={socketTop(0, 2)} color={SOCKET_COLORS.judge_result} />
        <SocketHandle kind="source" id="decomposition_features" label="decomposition_features"
          top={socketTop(1, 2)} color={SOCKET_COLORS.decomposition_features} />
      </>}
    />
  )
}
