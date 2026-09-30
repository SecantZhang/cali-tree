import { useEffect, useState } from 'react'
import { api } from '../../../api/client'
import { getRun, startRun, type StageRequest } from '../../../api/runs'
import { activeGraphStore, activeRunStore, useActiveGraphStore, useActiveRunStore } from '../../../store/activeTab'
import type { VeNode } from '../../../store/graphStore'
import { JudgeSamplePreview } from './JudgeSamplePreview'

type Ref = { run_id: string; node_id: string; stage: string; digest: string }
type Stage = { state?: string; source?: string; stale_inputs?: boolean; artifact_ref?: Ref; elapsed_ms?: number; usage?: unknown; original_usage?: unknown; completed?: number; total?: number }
type Report = { stages?: Record<string, Stage>; optimization?: unknown; decision_sets?: unknown; instruction_plans?: unknown; observations?: unknown; predictions?: unknown; validation?: unknown; children?: unknown; scope_overlap?: number }
type Partition = { fit_ids?: string[]; validation_ids?: string[]; test_ids?: string[]; samples?: Record<string, Record<string, unknown>>; labels?: Record<string, Record<string, unknown>> }
const LEAF = ['optimization', 'compilation', 'instruction_decomposition', 'evidence_checks', 'aggregation', 'validation']
const MERGE = ['synthesis', 'refinement', ...LEAF.slice(1)]
const VIEWS = ['Data', 'Stages', 'Optimization', 'Decision Sets', 'Validation']
const json = (value: unknown) => <pre style={{ whiteSpace: 'pre-wrap', overflowWrap: 'anywhere' }}>{JSON.stringify(value ?? {}, null, 2)}</pre>

export function CaliTreeManualPanel({ node }: { node: VeNode }) {
  const [view, setView] = useState('Data')
  const [search, setSearch] = useState('')
  const [preview, setPreview] = useState<string | null>(null)
  const [artifact, setArtifact] = useState<unknown>(null)
  const [error, setError] = useState('')
  const [launching, setLaunching] = useState(false)
  const edges = useActiveGraphStore(s => s.edges)
  const update = useActiveGraphStore(s => s.updateNodeParams)
  const outputs = useActiveRunStore(s => s.lastNodeResults)
  const partial = useActiveRunStore(s => s.partialResults[node.id])
  const runStatus = useActiveRunStore(s => s.status)
  const partitionSource = edges.find(e => e.target === node.id && e.targetHandle === 'partition')?.source
  const partition = (node.type === 'calitree_partition' ? outputs[node.id]?.outputs.partition : partitionSource ? outputs[partitionSource]?.outputs.partition : {}) as Partition | undefined
  const report = (partial?.outputs.calitree_report ?? outputs[node.id]?.outputs.calitree_report ?? {}) as Report
  const selected = (node.data.params.selected_ids ?? []) as string[]
  const pins = (node.data.params.stage_pins ?? {}) as Record<string, Ref>
  const savedRun = (node.data.params.artifact_run_id as string | undefined) ?? Object.values((node.data.params.stage_cache ?? pins) as Record<string, Ref>).at(-1)?.run_id
  useEffect(() => {
    if (!savedRun || activeRunStore().getState().runId) return
    let cancelled = false
    getRun(savedRun).then(result => {
      if (cancelled) return
      activeRunStore().getState().setLastNodeResults(result.node_results)
      activeRunStore().getState().attachRun(savedRun)
    }).catch(e => { if (!cancelled) setError(`Saved artifact hydration failed: ${String(e)}`) })
    return () => { cancelled = true }
  }, [savedRun])
  const views = node.type === 'calitree_partition' ? ['Data'] : VIEWS
  const stages = node.type === 'calitree_merge' ? MERGE : LEAF
  const busy = launching || ['running', 'stopping'].includes(runStatus)
  const filtered = (partition?.fit_ids ?? []).filter(id => `${id} ${JSON.stringify(partition?.samples?.[id] ?? {})}`.toLowerCase().includes(search.toLowerCase()))
  const tasks = [...new Set(filtered.map(id => String(partition?.samples?.[id]?.task_uid ?? id.split('::')[0])))]
  function toggle(ids: string[]) {
    const remove = ids.every(id => selected.includes(id))
    update(node.id, { selected_ids: remove ? selected.filter(id => !ids.includes(id)) : [...new Set([...selected, ...ids])].sort() })
  }
  async function run(request: StageRequest) {
    setError(''); setLaunching(true)
    try {
      const graph = activeGraphStore().getState()
      const state = activeRunStore().getState()
      if (!state.runId) throw new Error('Run the shared partition and node once before a stage action.')
      const metrics = request.action === 'metrics'
      if (!metrics && !state.dryRun && !window.confirm('This stage action will make real (billable) gateway calls. Continue?')) return
      const result = await startRun(graph.toJSON(), metrics ? false : state.dryRun, !metrics && !state.dryRun, graph.currentWorkflowName,
        { targetNodeId: node.id, runMode: 'self_only', seedRunId: state.runId, stageRequest: request })
      activeRunStore().getState().beginRun(result.run_id, 1, !metrics && !state.dryRun)
    } catch (e) { setError(e instanceof Error ? e.message : String(e)) }
    finally { setLaunching(false) }
  }
  function pin(stage: string) {
    const ref = report.stages?.[stage]?.artifact_ref
    if (!ref) return
    const cache = Object.fromEntries(Object.entries(report.stages ?? {}).filter(([, row]) => row.state === 'complete' && row.artifact_ref).map(([key, row]) => [key, row.artifact_ref]))
    update(node.id, { stage_pins: { ...pins, [stage]: ref }, stage_cache: cache })
  }
  async function inspect(ref: Ref) {
    try { setArtifact(await api.get(`/api/runs/${encodeURIComponent(ref.run_id)}/artifacts/${encodeURIComponent(ref.node_id)}/${ref.stage}/${ref.digest}`)) }
    catch (e) { setError(String(e)) }
  }
  return <div className="calitree-manual-panel">
    <div className="secondary-tab-strip" role="tablist">{views.map(label => <button role="tab" key={label} aria-selected={label === view} onClick={() => setView(label)}>{label}</button>)}</div>
    {error && <p role="alert">{error}</p>}
    {partial && <p>Live preview. Only completed stages with artifact references can be frozen.</p>}
    {view === 'Data' && <>
      <p>Fit {partition?.fit_ids?.length ?? 0} · reserved validation {partition?.validation_ids?.length ?? 0} · official test {partition?.test_ids?.length ?? 0}</p>
      {!partition?.fit_ids?.length && <p>Run AURORA → Dataset → shared partition to load selectable fit cases.</p>}
      {node.type === 'calitree_leaf' && <>
        <label>Search tasks or cases <input value={search} onChange={e => setSearch(e.target.value)} /></label>
        <p>{selected.length} selected fit cases</p>
        {tasks.map(task => <button key={task} disabled={busy || node.data.locked} onClick={() => toggle(filtered.filter(id => String(partition?.samples?.[id]?.task_uid ?? id.split('::')[0]) === task))}>Toggle task {task}</button>)}
        <div style={{ maxHeight: 280, overflow: 'auto' }}>{filtered.map(id => <div key={id}>
          <label><input type="checkbox" checked={selected.includes(id)} disabled={busy || node.data.locked} onChange={() => toggle([id])} />{id}</label>
          <button onClick={() => setPreview(id)}>Preview</button>
        </div>)}</div>
      </>}
      {node.type === 'calitree_merge' && <>{json(report.children)}<p>Overlapping cases deduplicated: {report.scope_overlap ?? 0}</p></>}
      {preview && partition?.samples?.[preview] && <JudgeSamplePreview item={partition.samples[preview]} label={partition.labels?.[preview]} />}
    </>}
    {view === 'Stages' && <>
      <p>Freezing pins this stage’s exact artifact. Canvas ancestors remain editable. Changed inputs are shown as stale; incompatible bindings stop execution.</p>
      <table><thead><tr><th>Stage</th><th>Status / source</th><th>Time / usage</th><th>Actions</th></tr></thead><tbody>
        {stages.map(stage => { const row = report.stages?.[stage]; return <tr key={stage}>
          <td>{stage}</td><td>{row?.state ?? 'pending'} · {pins[stage] ? 'pinned' : row?.source ?? '—'}{row?.stale_inputs && ' · inputs differ'}{row?.total != null && ` · ${row.completed ?? 0}/${row.total}`}</td>
          <td>{row?.elapsed_ms ?? 0} ms{json(row?.usage)}</td><td>
            <button disabled={busy || node.data.locked} onClick={() => run({ run_until: stage })}>Run through</button>
            <button disabled={busy || node.data.locked} onClick={() => run({ run_from: stage, run_until: String(node.data.params.run_until ?? 'validation') })}>Rerun from</button>
            {pins[stage] ? <button disabled={busy || node.data.locked} onClick={() => { const next = { ...pins }; delete next[stage]; update(node.id, { stage_pins: next }) }}>Unfreeze</button> : <button disabled={busy || node.data.locked || row?.state !== 'complete' || !row.artifact_ref} onClick={() => pin(stage)}>Freeze</button>}
            {(pins[stage] ?? row?.artifact_ref) && <button onClick={() => inspect(pins[stage] ?? row!.artifact_ref!)}>Inspect original artifact</button>}
          </td></tr> })}
      </tbody></table>{artifact != null && json(artifact)}
    </>}
    {view === 'Optimization' && <>{json(report.optimization)}</>}
    {view === 'Decision Sets' && <><h4>Compiled policy</h4>{json(report.decision_sets)}<h4>Instruction plans</h4>{json(report.instruction_plans)}<h4>Evidence checks</h4>{json(report.observations)}<h4>Traces and predictions</h4>{json(report.predictions)}</>}
    {view === 'Validation' && <>
      <button disabled={busy || node.data.locked} onClick={() => run({ action: 'metrics' })}>Recompute metrics</button>
      <button disabled={busy || node.data.locked || ['evidence_checks', 'aggregation', 'validation'].some(s => pins[s])} onClick={() => run({ action: 'fresh' })}>Fresh evaluation</button>
      <p>Recompute uses saved predictions without model calls. Fresh evaluation bypasses execution caches; unfreeze evidence checks, aggregation and validation first.</p>
      {json(report.validation)}{json(report.predictions)}
    </>}
  </div>
}
