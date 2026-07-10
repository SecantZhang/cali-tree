import type { NodeProps } from '@xyflow/react'
import { NODE_PARAM_SCHEMAS } from './paramSchemas'
import { SimpleParamNode } from './SimpleParamNode'
import { SocketHandle, socketTop } from './SocketHandle'
import { SOCKET_COLORS } from './socketTypes'
import type { VeNodeData } from './types'

export function JudgeNode({ id, data, selected }: NodeProps) {
  const d = data as VeNodeData
  return (
    <SimpleParamNode
      id={id}
      data={d}
      selected={selected}
      title="Judge"
      color="var(--node-vejudge)"
      schema={NODE_PARAM_SCHEMAS.judge}
      summaryLine={(p) => `batch: ${p.batch_size ?? 1}`}
      sockets={
        <>
          <SocketHandle
            kind="target" id="samples" label="samples" top={socketTop(0, 3)}
            color={SOCKET_COLORS.samples}
          />
          <SocketHandle
            kind="target" id="engine_config" label="engine_config" top={socketTop(1, 3)}
            color={SOCKET_COLORS.engine_config}
          />
          <SocketHandle
            kind="target" id="judge_spec" label="judge_spec" top={socketTop(2, 3)}
            color={SOCKET_COLORS.judge_spec}
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
