import type { ReactNode } from 'react'
import { startRun } from '../api/runs'
import { activeGraphStore, activeRunStore, useActiveGraphStore, useActiveRunStore } from '../store/activeTab'
import { liveRunInAnotherTab } from '../store/liveRunGuard'
import { ancestorsOf, descendantsOf } from './graphTraversal'
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
  // See NodeChrome's socketZoneHeight — only needed by a node with many sockets on one side.
  socketZoneHeight?: number
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
 * every concrete node file (PeanutSourceNode, DatasetNode, JudgeNode, ...) reduces to
 * supplying its title/color/schema/sockets. Collapsed-summary/param-mapping/status-
 * progress wiring live here once instead of being copied per node type.
 */
export function SimpleParamNode({
  id, data, selected, title, color, schema, sockets, socketZoneHeight, summaryLine, staticBody,
  fieldOverrides,
}: SimpleParamNodeProps) {
  const updateNodeParams = useActiveGraphStore((s) => s.updateNodeParams)
  const toggleNodeCollapsed = useActiveGraphStore((s) => s.toggleNodeCollapsed)
  const nodes = useActiveGraphStore((s) => s.nodes)
  const edges = useActiveGraphStore((s) => s.edges)
  const lockNodes = useActiveGraphStore((s) => s.lockNodes)
  const unlockNodes = useActiveGraphStore((s) => s.unlockNodes)
  const progress = useActiveRunStore((s) => s.nodeProgress[id])
  const runOrder = useActiveRunStore((s) => s.runOrder)
  const stale = useActiveRunStore((s) => s.staleNodeIds.has(id))
  const priorRunId = useActiveRunStore((s) => s.runId)
  const runStatus = useActiveRunStore((s) => s.status)
  const lastRunNodeIds = useActiveRunStore((s) => s.lastRunNodeIds)
  const hasParams = Object.keys(schema).length > 0

  // Lock is only offerable once this node AND all its ancestors have a real result in the
  // *most recent run* (`lastRunNodeIds`), not merely a cosmetic `done` status — since a lock
  // reuses (seeds) those results from that run. Gating on `done` alone let you lock a node
  // whose "done" came from a loaded workflow (or a scoped run that didn't cover it), which
  // then failed at run time with "prior run has no result for locked node(s)".
  const lockChainReady = [id, ...ancestorsOf(edges, id)].every(
    (nid) =>
      lastRunNodeIds.has(nid) && nodes.find((n) => n.id === nid)?.data.status === 'done',
  )
  // The lock button acts on the whole current selection (multi-select), always including
  // this node; falls back to just this node when nothing else is selected.
  const handleToggleLock = () => {
    const selectedIds = nodes.filter((n) => n.selected).map((n) => n.id)
    const targets = selectedIds.includes(id) && selectedIds.length > 0 ? selectedIds : [id]
    if (data.locked) unlockNodes(targets)
    else lockNodes(targets)
  }

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
    const { edges, currentWorkflowName, nodes } = graphStore.getState()
    runStore.getState().markNodesStale(descendantsOf(edges, id))
    const lockedNodeIds = nodes.filter((n) => n.data.locked).map((n) => n.id)
    const seedRunId = runStore.getState().runId
    try {
      const graph = graphStore.getState().toJSON()
      const result = await startRun(
        graph, dryRun, !dryRun, currentWorkflowName,
        { targetNodeId: id, runMode: 'ancestors' },
        lockedNodeIds.length ? { nodeIds: lockedNodeIds, seedRunId } : undefined,
      )
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
      socketZoneHeight={socketZoneHeight}
      orderIndex={orderIndex}
      stale={stale}
      locked={data.locked}
      onRun={handleRun}
      onRerun={handleRerun}
      onToggleLock={handleToggleLock}
      lockDisabledReason={lockChainReady ? null : 'Run this node (and its inputs) to completion first — a lock reuses that run’s result'}
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
          // A locked node's params are read-only (its result is frozen/reused) — the
          // `params-locked` class disables interaction (see App.css).
          <div className={data.locked ? 'params-locked' : undefined}>
            {Object.entries(schema).map(([key, field]) => {
              const onChange = (v: unknown) => updateNodeParams(id, { [key]: v })
              const override = fieldOverrides?.[key]
              if (override) {
                return <div key={key}>{override(data.params[key], onChange, data.params)}</div>
              }
              return (
                <ParamField key={key} name={key} field={field} value={data.params[key]} onChange={onChange} />
              )
            })}
          </div>
        )
      )}
    </NodeChrome>
  )
}
