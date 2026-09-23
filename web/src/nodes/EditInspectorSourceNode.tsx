import type { NodeProps } from '@xyflow/react'
import { NODE_PARAM_SCHEMAS } from './paramSchemas'
import { SimpleParamNode } from './SimpleParamNode'
import { SocketHandle, socketTop } from './SocketHandle'
import { SOCKET_COLORS } from './socketTypes'
import type { VeNodeData } from './types'

export function EditInspectorSourceNode({ id, data, selected }: NodeProps) {
  const d = data as VeNodeData
  return (
    <SimpleParamNode
      id={id} data={d} selected={selected}
      title="EditInspector Source" color="var(--node-db)"
      schema={NODE_PARAM_SCHEMAS.editinspector_source}
      summaryLine={(params) => `${String(params.partition ?? 'all')} · 3 human raters`}
      sockets={
        <>
          <SocketHandle kind="source" id="raw_dataset" label="raw_dataset" top={socketTop(0, 2)} color={SOCKET_COLORS.raw_dataset} />
          <SocketHandle kind="source" id="raw_labels" label="raw_labels" top={socketTop(1, 2)} color={SOCKET_COLORS.raw_labels} />
        </>
      }
    />
  )
}
