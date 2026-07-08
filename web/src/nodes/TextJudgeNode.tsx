import type { NodeProps } from '@xyflow/react'
import { NODE_PARAM_SCHEMAS } from './paramSchemas'
import { SimpleParamNode } from './SimpleParamNode'
import { SocketHandle, socketTop } from './SocketHandle'
import { SOCKET_COLORS } from './socketTypes'
import type { VeNodeData } from './types'

export function TextJudgeNode({ id, data, selected }: NodeProps) {
  const d = data as VeNodeData
  return (
    <SimpleParamNode
      id={id}
      data={d}
      selected={selected}
      title="Text Judge"
      color="var(--node-vejudge)"
      schema={NODE_PARAM_SCHEMAS.judge_text}
      summaryLine={(p) => {
        const metrics = (p.metrics as string[] | null) ?? []
        return `metrics: ${metrics.length ? metrics.join(', ') : 'all'}`
      }}
      sockets={
        <>
          <SocketHandle
            kind="target" id="dataset" label="dataset" top={socketTop(0, 2)}
            color={SOCKET_COLORS.dataset}
          />
          <SocketHandle
            kind="target" id="engine_config" label="engine_config" top={socketTop(1, 2)}
            color={SOCKET_COLORS.engine_config}
          />
          <SocketHandle
            kind="source" id="judge_result" label="judge_result" top={socketTop(0, 1)}
            color={SOCKET_COLORS.judge_result}
          />
        </>
      }
    />
  )
}
