import type { NodeProps } from '@xyflow/react'
import { NODE_PARAM_SCHEMAS } from './paramSchemas'
import { SimpleParamNode } from './SimpleParamNode'
import { SocketHandle, socketTop } from './SocketHandle'
import { SOCKET_COLORS } from './socketTypes'
import type { VeNodeData } from './types'

// Custom-only params — hidden unless preset === "custom" so a builtin preset stays a
// one-field node.
const CUSTOM_ONLY = new Set([
  'spec_id', 'label', 'modality', 'system', 'user_template',
  'expected_fields', 'score_path', 'target_dimension',
])

export function JudgePromptNode({ id, data, selected }: NodeProps) {
  const d = data as VeNodeData
  const isCustom = (d.params.preset ?? 'M1') === 'custom'
  const schema = NODE_PARAM_SCHEMAS.judge_prompt
  const visibleSchema = isCustom
    ? schema
    : Object.fromEntries(Object.entries(schema).filter(([k]) => !CUSTOM_ONLY.has(k)))

  return (
    <SimpleParamNode
      id={id}
      data={d}
      selected={selected}
      title="Judge Prompt"
      color="var(--node-vejudge)"
      schema={visibleSchema}
      summaryLine={(p) => `metric: ${p.preset ?? 'M1'}`}
      sockets={
        <SocketHandle
          kind="source" id="judge_spec" label="judge_spec" top={socketTop(0, 1)}
          color={SOCKET_COLORS.judge_spec}
        />
      }
    />
  )
}
