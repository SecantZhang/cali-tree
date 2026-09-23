import type { NodeProps } from '@xyflow/react'
import { SimpleParamNode } from './SimpleParamNode'
import { SocketHandle, socketTop } from './SocketHandle'
import { SOCKET_COLORS } from './socketTypes'
import type { VeNodeData } from './types'

export function CaliTreeEvalNode({ id, data, selected }: NodeProps) {
  const d = data as VeNodeData
  return (
    <SimpleParamNode
      id={id} data={d} selected={selected}
      title="Cali-Tree Eval" color="var(--node-eval)" schema={{}}
      sockets={
        <>
          <SocketHandle kind="target" id="judge_result" label="judge_result" top={socketTop(0, 3)} color={SOCKET_COLORS.judge_result} />
          <SocketHandle kind="target" id="labels" label="labels" top={socketTop(1, 3)} color={SOCKET_COLORS.labels} />
          <SocketHandle kind="target" id="samples" label="samples" top={socketTop(2, 3)} color={SOCKET_COLORS.samples} />
          <SocketHandle kind="source" id="metrics_report" label="metrics_report" top={socketTop(0, 1)} color={SOCKET_COLORS.metrics_report} />
        </>
      }
    />
  )
}
