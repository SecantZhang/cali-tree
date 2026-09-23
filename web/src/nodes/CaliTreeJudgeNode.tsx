import type { NodeProps } from '@xyflow/react'
import { NODE_PARAM_SCHEMAS } from './paramSchemas'
import { SimpleParamNode } from './SimpleParamNode'
import { SocketHandle, socketTop } from './SocketHandle'
import { SOCKET_COLORS } from './socketTypes'
import type { VeNodeData } from './types'

export function CaliTreeJudgeNode({ id, data, selected }: NodeProps) {
  const d = data as VeNodeData
  return (
    <SimpleParamNode
      id={id} data={d} selected={selected}
      title="Cali-Tree Judge" color="var(--node-vejudge)"
      schema={NODE_PARAM_SCHEMAS.calitree_judge}
      sockets={
        <>
          <SocketHandle kind="target" id="samples" label="samples" top={socketTop(0, 3)} color={SOCKET_COLORS.samples} />
          <SocketHandle kind="target" id="prompt_tree" label="prompt_tree" top={socketTop(1, 3)} color={SOCKET_COLORS.prompt_tree} />
          <SocketHandle kind="target" id="judge_engine" label="judge_engine" top={socketTop(2, 3)} color={SOCKET_COLORS.engine_config} />
          <SocketHandle kind="source" id="judge_result" label="judge_result" top={socketTop(0, 1)} color={SOCKET_COLORS.judge_result} />
        </>
      }
    />
  )
}
