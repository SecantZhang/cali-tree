import type { NodeProps } from '@xyflow/react'
import { useActiveGraphStore } from '../store/activeTab'
import { modelsFor } from './modelCatalog'
import { NODE_PARAM_SCHEMAS } from './paramSchemas'
import { SimpleParamNode } from './SimpleParamNode'
import { SocketHandle, socketTop } from './SocketHandle'
import { SOCKET_COLORS } from './socketTypes'
import type { VeNodeData } from './types'

const ENGINE_KIND_OPTIONS = NODE_PARAM_SCHEMAS.lm_engine.engine_kind.options ?? []

export function LMEngineNode({ id, data, selected }: NodeProps) {
  const d = data as VeNodeData
  const updateNodeParams = useActiveGraphStore((s) => s.updateNodeParams)
  return (
    <SimpleParamNode
      id={id}
      data={d}
      selected={selected}
      title="LM Engine"
      color="var(--node-lm-engine)"
      schema={NODE_PARAM_SCHEMAS.lm_engine}
      summaryLine={(p) => `engine: ${p.engine_kind ?? 'gpt'} / ${p.model ?? '(default)'}`}
      fieldOverrides={{
        // The model dropdown's options depend on the sibling engine_kind value, which a
        // static per-key ParamField schema can't express — so both fields are overridden
        // together: changing engine_kind also resets model to the new kind's first option
        // whenever the current model isn't valid for it, so the two params never drift out
        // of sync (e.g. a leftover "gpt-4.1" after switching to "claude").
        engine_kind: (value, onChange, allParams) => (
          <div className="param-row nodrag nopan">
            <label className="param-label">engine_kind</label>
            <select
              value={(value as string) ?? 'gpt'}
              onChange={(e) => {
                const nextKind = e.target.value
                onChange(nextKind)
                const validModels = modelsFor(nextKind)
                if (!validModels.includes(allParams.model as string)) {
                  updateNodeParams(id, { model: validModels[0] ?? null })
                }
              }}
            >
              {ENGINE_KIND_OPTIONS.map((opt) => (
                <option key={opt} value={opt}>{opt}</option>
              ))}
            </select>
          </div>
        ),
        model: (value, onChange, allParams) => {
          const options = modelsFor((allParams.engine_kind as string) ?? 'gpt')
          return (
            <div className="param-row nodrag nopan">
              <label className="param-label">model</label>
              <select value={(value as string) ?? options[0] ?? ''} onChange={(e) => onChange(e.target.value)}>
                {options.map((opt) => (
                  <option key={opt} value={opt}>{opt}</option>
                ))}
              </select>
            </div>
          )
        },
      }}
      sockets={
        <SocketHandle
          kind="source" id="engine_config" label="engine_config" top={socketTop(0, 1)}
          color={SOCKET_COLORS.engine_config}
        />
      }
    />
  )
}
