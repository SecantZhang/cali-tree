import type { NodeProps } from '@xyflow/react'
import { SimpleParamNode } from './SimpleParamNode'
import { SocketHandle, socketTop } from './SocketHandle'
import { NODE_PARAM_SCHEMAS } from './paramSchemas'
import { NODE_SOCKETS, SOCKET_COLORS } from './socketTypes'
import type { VeNodeData } from './types'
import { useActiveRunStore } from '../store/activeTab'

export function CaliTreeManualNode({ id, data, selected, type }: NodeProps) {
  const d = data as VeNodeData
  const result = useActiveRunStore(s => s.lastNodeResults[id])
  const sockets = NODE_SOCKETS[type ?? 'calitree_leaf']
  const titles: Record<string, string> = { aurora_source: 'AURORA Source', calitree_partition: 'CaliTree Partition', calitree_leaf: 'CaliTree Leaf', calitree_merge: 'CaliTree Merge' }
  return <SimpleParamNode id={id} data={d} selected={selected} title={titles[type ?? '']} color="var(--node-calibration)"
    schema={NODE_PARAM_SCHEMAS[type ?? '']} socketZoneHeight={100}
    fieldOverrides={{ selected_ids: value => <span>{Array.isArray(value) ? value.length : 0} fit cases · select in Data tab</span> }}
    sockets={<>{(['input', 'output'] as const).flatMap(side => Object.entries(sockets[side]).map(([name, socket], index, all) => {
      const optional = ['optimized_prompt', 'decision_sets'].includes(name)
      const readiness = result?.meta.output_readiness as Record<string, boolean> | undefined
      const disabled = optional && (readiness ? !readiness[name] : name === 'decision_sets')
      return <SocketHandle key={side + name} kind={side === 'input' ? 'target' : 'source'} id={name}
        label={disabled ? `${name} (unavailable)` : name} top={socketTop(index, all.length)} color={SOCKET_COLORS[socket]} disabled={disabled} />
    }))}</>} />
}
