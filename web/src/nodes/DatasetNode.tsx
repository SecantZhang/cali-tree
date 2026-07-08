import type { NodeProps } from '@xyflow/react'
import { NODE_PARAM_SCHEMAS } from './paramSchemas'
import { SimpleParamNode } from './SimpleParamNode'
import { SocketHandle, socketTop } from './SocketHandle'
import { SOCKET_COLORS } from './socketTypes'
import type { VeNodeData } from './types'

export function DatasetNode({ id, data, selected }: NodeProps) {
  const d = data as VeNodeData
  return (
    <SimpleParamNode
      id={id}
      data={d}
      selected={selected}
      title="Dataset"
      color="var(--node-db)"
      schema={NODE_PARAM_SCHEMAS.dataset}
      summaryLine={(p) => `sampling: ${p.sampling_mode ?? 'unified'}`}
      sockets={
        <>
          <SocketHandle
            kind="target" id="raw_dataset" label="raw_dataset" top={socketTop(0, 1)}
            color={SOCKET_COLORS.raw_dataset}
          />
          <SocketHandle
            kind="source" id="dataset" label="dataset" top={socketTop(0, 2)}
            color={SOCKET_COLORS.dataset}
          />
          <SocketHandle
            kind="source" id="labels" label="labels" top={socketTop(1, 2)}
            color={SOCKET_COLORS.labels}
          />
        </>
      }
    />
  )
}
