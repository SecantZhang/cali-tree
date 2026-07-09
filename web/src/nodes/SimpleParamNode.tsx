import type { ReactNode } from 'react'
import { startRun } from '../api/runs'
import { activeGraphStore, activeRunStore, useActiveGraphStore, useActiveRunStore } from '../store/activeTab'
import { liveRunInAnotherTab } from '../store/liveRunGuard'
import { descendantsOf } from './graphTraversal'
import { NodeChrome } from './NodeChrome'
import { ParamField } from './ParamField'
import type { ParamField as ParamFieldSchema } from './paramSchemas'
import type { VeNodeData } from './types'

interface SimpleParamNodeProps {
  id: string
  data: VeNodeData
  selected?: boolean
  title: string
  color: string
  schema: Record<string, ParamFieldSchema>
  sockets: ReactNode
  // One-line text shown instead of the full param list once collapsed (only relevant
  // when `schema` is non-empty — a schema-less node like Eval never offers collapse).
  summaryLine?: (params: Record<string, unknown>) => string
  // Static body content for a node with no params at all (e.g. Eval) — shown unconditionally.
  staticBody?: ReactNode
  // Per-field escape hatch from the generic schema-driven ParamField render — e.g. the LM
  // Engine Node's `model` field renders a dropdown scoped to the sibling `engine_kind`
  // value instead of a free-text input, which the static per-key `schema` alone can't
  // express. A key with no override here falls back to the default ParamField render.
  fieldOverrides?: Record<
    string,
    (value: unknown, onChange: (v: unknown) => void, allParams: Record<string, unknown>) => ReactNode
  >
}

/**
 * Shared shell for every node type that's just "sockets + a schema-driven param list" —
 * every concrete node file (PeanutSourceNode, DatasetNode, TextJudgeNode, ...) reduces to
 * supplying its title/color/schema/sockets. Collapsed-summary/param-mapping/status-
 * progress wiring live here once instead of being copied per node type.
 */
export function SimpleParamNode({
  id, data, selected, title, color, schema, sockets, summaryLine, staticBody, fieldOverrides,
}: SimpleParamNodeProps) {
  const updateNodeParams = useActiveGraphStore((s) => s.updateNodeParams)
  const toggleNodeCollapsed = useActiveGraphStore((s) => s.toggleNodeCollapsed)
  const progress = useActiveRunStore((s) => s.nodeProgress[id])
  const runOrder = useActiveRunStore((s) => s.runOrder)
  const stale = useActiveRunStore((s) => s.staleNodeIds.has(id))
  const priorRunId = useActiveRunStore((s) => s.runId)
  const runStatus = useActiveRunStore((s) => s.status)
  const hasParams = Object.keys(schema).length > 0

  const orderIdx = runOrder.indexOf(id)
  const orderIndex = orderIdx >= 0 ? orderIdx + 1 : null
  const running = runStatus === 'running' || runStatus === 'stopping'

  // Both buttons show the same --live confirmation the global Run button does (RunControls
  // .tsx) — a per-node run is just as capable of making real, billable gateway calls.
  const confirmLiveIfNeeded = (dryRun: boolean): boolean => {
    if (dryRun) return true
    const warning = liveRunInAnotherTab()
      ? 'Another open tab has a live run in progress right now. '
      : ''
    return window.confirm(
      `${warning}This run will make real (billable) gateway calls. Continue with --live?`,
    )
  }

  const handleRun = async () => {
    const runStore = activeRunStore()
    const graphStore = activeGraphStore()
    const { dryRun } = runStore.getState()
    if (!confirmLiveIfNeeded(dryRun)) return
    const { edges, currentWorkflowName } = graphStore.getState()
    runStore.getState().markNodesStale(descendantsOf(edges, id))
    try {
      const graph = graphStore.getState().toJSON()
      const result = await startRun(graph, dryRun, !dryRun, currentWorkflowName, {
        targetNodeId: id, runMode: 'ancestors',
      })
      runStore.getState().beginRun(result.run_id, graph.nodes.length, !dryRun)
    } catch (e) {
      window.alert(e instanceof Error ? e.message : String(e))
    }
  }

  const handleRerun = async () => {
    const runStore = activeRunStore()
    const graphStore = activeGraphStore()
    const { dryRun, runId: seedRunId } = runStore.getState()
    if (!seedRunId) return
    if (!confirmLiveIfNeeded(dryRun)) return
    const { edges, currentWorkflowName } = graphStore.getState()
    runStore.getState().markNodesStale(descendantsOf(edges, id))
    try {
      const graph = graphStore.getState().toJSON()
      const result = await startRun(graph, dryRun, !dryRun, currentWorkflowName, {
        targetNodeId: id, runMode: 'self_only', seedRunId,
      })
      runStore.getState().beginRun(result.run_id, 1, !dryRun)
    } catch (e) {
      window.alert(e instanceof Error ? e.message : String(e))
    }
  }

  return (
    <NodeChrome
      title={title} color={color} status={data.status} error={data.error}
      collapsed={data.collapsed}
      onToggleCollapse={hasParams ? () => toggleNodeCollapsed(id) : undefined}
      progress={progress} selected={selected} sockets={sockets}
      orderIndex={orderIndex}
      stale={stale}
      onRun={handleRun}
      onRerun={handleRerun}
      runDisabledReason={running ? 'A run is already in progress' : null}
      rerunDisabledReason={
        running
          ? 'A run is already in progress'
          : !priorRunId
            ? 'Run the graph at least once before Re-run is available'
            : null
      }
    >
      {!hasParams && staticBody}
      {hasParams && (
        data.collapsed ? (
          <div className="rf-node-param">{summaryLine ? summaryLine(data.params) : ''}</div>
        ) : (
          Object.entries(schema).map(([key, field]) => {
            const onChange = (v: unknown) => updateNodeParams(id, { [key]: v })
            const override = fieldOverrides?.[key]
            if (override) {
              return <div key={key}>{override(data.params[key], onChange, data.params)}</div>
            }
            return (
              <ParamField key={key} name={key} field={field} value={data.params[key]} onChange={onChange} />
            )
          })
        )
      )}
    </NodeChrome>
  )
}
