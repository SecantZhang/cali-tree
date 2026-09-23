import type { NodeProps } from '@xyflow/react'
import { NODE_PARAM_SCHEMAS } from './paramSchemas'
import { SimpleParamNode } from './SimpleParamNode'
import { SocketHandle, socketTop } from './SocketHandle'
import { SOCKET_COLORS } from './socketTypes'
import type { VeNodeData } from './types'

export function ImagenHubSourceNode({ id, data, selected }: NodeProps) {
  const d = data as VeNodeData
  return (
    <SimpleParamNode
      id={id} data={d} selected={selected}
      title="ImagenHub Source" color="var(--node-db)"
      schema={NODE_PARAM_SCHEMAS.imagenhub_source}
      summaryLine={(p) => `repeat ${p.repeat ?? 1} · ${Array.isArray(p.editors) ? p.editors.length : 9} editors`}
      sockets={
        <>
          <SocketHandle kind="source" id="raw_dataset" label="raw_dataset" top={socketTop(0, 2)} color={SOCKET_COLORS.raw_dataset} />
          <SocketHandle kind="source" id="raw_labels" label="raw_labels" top={socketTop(1, 2)} color={SOCKET_COLORS.raw_labels} />
        </>
      }
    />
  )
}
