import type { NodeProps } from '@xyflow/react'
import { NODE_PARAM_SCHEMAS } from './paramSchemas'
import { SimpleParamNode } from './SimpleParamNode'
import { SocketHandle, socketTop } from './SocketHandle'
import { SOCKET_COLORS } from './socketTypes'
import type { VeNodeData } from './types'

export function RubricLiteBoundaryNode({ id, data, selected }: NodeProps) {
  const d = data as VeNodeData
  return (
    <SimpleParamNode
      id={id} data={d} selected={selected}
      title="Partial Boundary Verifier" color="var(--node-calibration)"
      schema={NODE_PARAM_SCHEMAS.rubric_lite_boundary}
      summaryLine={(p) => (
        `verify score ≥ ${Number(p.minimum_ordinal_score ?? 50)} · ${String(p.apply_split ?? 'all')}`
      )}
      socketZoneHeight={80}
      sockets={
        <>
          {['samples', 'judge_result', 'judge_engine'].map((name, index) => (
            <SocketHandle
              key={name} kind="target" id={name} label={name} top={socketTop(index, 3)}
              color={
                name === 'samples' ? SOCKET_COLORS.samples
                  : name === 'judge_result' ? SOCKET_COLORS.judge_result
                    : SOCKET_COLORS.engine_config
              }
            />
          ))}
          <SocketHandle
            kind="source" id="judge_result" label="judge_result"
            top={socketTop(0, 1)} color={SOCKET_COLORS.judge_result}
          />
        </>
      }
    />
  )
}
