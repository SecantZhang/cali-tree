import type { NodeProps } from '@xyflow/react'
import { NODE_PARAM_SCHEMAS } from './paramSchemas'
import { SimpleParamNode } from './SimpleParamNode'
import { SocketHandle, socketTop } from './SocketHandle'
import { SOCKET_COLORS } from './socketTypes'
import type { VeNodeData } from './types'

export function CaliTreeTrainNode({ id, data, selected }: NodeProps) {
  const d = data as VeNodeData
  return (
    <SimpleParamNode
      id={id} data={d} selected={selected}
      title="Cali-Tree Train" color="var(--node-calibration)"
      schema={NODE_PARAM_SCHEMAS.calitree_train}
      summaryLine={(p) => `${p.max_steps ?? 3} steps · merge ≥ ${p.merge_acceptance ?? 0.8}`}
      socketZoneHeight={90}
      sockets={
        <>
          {['samples', 'labels', 'judge_engine', 'optimizer_engine'].map((name, index) => (
            <SocketHandle
              key={name} kind="target" id={name} label={name} top={socketTop(index, 4)}
              color={
                name === 'samples' ? SOCKET_COLORS.samples
                  : name === 'labels' ? SOCKET_COLORS.labels
                    : SOCKET_COLORS.engine_config
              }
            />
          ))}
          <SocketHandle kind="source" id="prompt_tree" label="prompt_tree" top={socketTop(0, 2)} color={SOCKET_COLORS.prompt_tree} />
          <SocketHandle kind="source" id="calitree_report" label="calitree_report" top={socketTop(1, 2)} color={SOCKET_COLORS.calitree_report} />
        </>
      }
    />
  )
}
