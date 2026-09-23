import type { NodeProps } from '@xyflow/react'
import { NODE_PARAM_SCHEMAS } from './paramSchemas'
import { SimpleParamNode } from './SimpleParamNode'
import { SocketHandle, socketTop } from './SocketHandle'
import { SOCKET_COLORS } from './socketTypes'
import type { VeNodeData } from './types'

export function DatasetNode({ id, data, selected }: NodeProps) {
  const d = data as VeNodeData
  // Split-specific controls are useful for calibration workflows but make every ordinary
  // video Dataset node needlessly tall. Reveal them only when their sampling mode can use
  // them; the values remain in node params and the backend schema remains authoritative.
  const splitControls = new Set([
    'train_sampling_ratio',
    'test_sampling_ratio',
    'test_group_offset',
    'group_by_task',
  ])
  const schema = Object.fromEntries(
    Object.entries(NODE_PARAM_SCHEMAS.dataset).filter(
      ([key]) => (
        d.params.sampling_mode === 'split_label_stratified'
        || !splitControls.has(key)
      ),
    ),
  )
  return (
    <SimpleParamNode
      id={id}
      data={d}
      selected={selected}
      title="Dataset"
      color="var(--node-db)"
      schema={schema}
      summaryLine={(p) => `sampling: ${p.sampling_mode ?? 'unified'}`}
      sockets={
        <>
          <SocketHandle
            kind="target" id="raw_dataset" label="raw_dataset" top={socketTop(0, 2)}
            color={SOCKET_COLORS.raw_dataset}
          />
          <SocketHandle
            kind="target" id="raw_labels" label="raw_labels" top={socketTop(1, 2)}
            color={SOCKET_COLORS.raw_labels}
          />
          <SocketHandle
            kind="source" id="samples" label="samples" top={socketTop(0, 2)}
            color={SOCKET_COLORS.samples}
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
