import { fireEvent, render, screen } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { activeGraphStore, activeRunStore, useActiveGraphStore } from '../../../store/activeTab'
import { useTabsStore } from '../../../store/tabsStore'
import { CaliTreeManualPanel } from './CaliTreeManualPanel'
import { isMultiInputSocket, isValidSocketConnection } from '../../../nodes/socketTypes'
import { defaultParamsFor } from '../../../nodes/paramSchemas'

function setup() {
  useTabsStore.getState().openBlankTab()
  activeGraphStore().getState().addNode('calitree_leaf', { x: 0, y: 0 })
  const node = activeGraphStore().getState().nodes[0]
  activeGraphStore().setState({ edges: [{ id: 'partition-edge', source: 'partition', target: node.id, targetHandle: 'partition', sourceHandle: 'partition' }] })
  activeRunStore().getState().setLastNodeResults({ partition: { status: 'done', error: null, meta: {}, outputs: { partition: {
    fit_ids: ['fit::a', 'fit::b'], validation_ids: ['reserved'], test_ids: ['test'],
    samples: { 'fit::a': { item_id: 'fit::a', task_uid: 'color', input: { instruction: 'red' } }, 'fit::b': { item_id: 'fit::b', task_uid: 'remove', input: { instruction: 'remove sphere' } }, reserved: { task_uid: 'SECRET_VALIDATION' } },
  } } } })
  function Panel() { const current = useActiveGraphStore(s => s.nodes.find(n => n.id === node.id)!); return <CaliTreeManualPanel node={current} /> }
  return { node, Panel }
}

beforeEach(() => vi.restoreAllMocks())

describe('manual CaliTree workflow', () => {
  it('registers fan-in children, typed artifacts and independent defaults', () => {
    expect(isMultiInputSocket('calitree_merge', 'children')).toBe(true)
    expect(isValidSocketConnection('calitree_leaf', 'node', 'calitree_merge', 'children')).toBe(true)
    expect(isValidSocketConnection('calitree_merge', 'node', 'calitree_judge', 'calitree_node')).toBe(true)
    expect(isValidSocketConnection('calitree_leaf', 'optimized_prompt', 'calitree_merge', 'children')).toBe(false)
    expect(defaultParamsFor('calitree_leaf')).toMatchObject({ optimizer_plan: 'textgrad', optimization_evaluator: 'raw_prompt', decomposition_strategy: 'two_way_vision', selected_ids: [] })
    expect(defaultParamsFor('calitree_partition')).toMatchObject({ validation_fraction: .25, seed: 44 })
  })
  it('only offers fit cases, searches tasks, and persists explicit selections', () => {
    const { node, Panel } = setup()
    render(<Panel />)
    expect(screen.queryByText('SECRET_VALIDATION')).not.toBeInTheDocument()
    fireEvent.change(screen.getByLabelText('Search tasks or cases'), { target: { value: 'color' } })
    expect(screen.queryByLabelText('fit::b')).not.toBeInTheDocument()
    fireEvent.click(screen.getByLabelText('fit::a'))
    expect(activeGraphStore().getState().nodes[0].data.params.selected_ids).toEqual(['fit::a'])
    expect(activeGraphStore().getState().toJSON().nodes.find(n => n.id === node.id)?.params.selected_ids).toEqual(['fit::a'])
  })
  it('freezes only complete artifacts without locking ancestors and disables fresh evaluation', () => {
    const { node, Panel } = setup()
    const ref = { run_id: 'saved', node_id: node.id, stage: 'evidence_checks', digest: 'a'.repeat(64) }
    activeRunStore().getState().setLastNodeResults({ [node.id]: { status: 'done', error: null, meta: {}, outputs: { calitree_report: { stages: { evidence_checks: { state: 'complete', source: 'computed', artifact_ref: ref } } } } } })
    render(<Panel />)
    fireEvent.click(screen.getByRole('tab', { name: 'Stages' }))
    const freeze = screen.getAllByRole('button', { name: 'Freeze' })
    expect(freeze.filter(b => !(b as HTMLButtonElement).disabled)).toHaveLength(1)
    fireEvent.click(freeze.find(b => !(b as HTMLButtonElement).disabled)!)
    expect(activeGraphStore().getState().nodes[0].data.params.stage_pins).toEqual({ evidence_checks: ref })
    expect(activeGraphStore().getState().nodes[0].data.locked).toBeFalsy()
    fireEvent.click(screen.getByRole('tab', { name: 'Validation' }))
    expect(screen.getByRole('button', { name: 'Fresh evaluation' })).toBeDisabled()
    expect(screen.getByRole('button', { name: 'Recompute metrics' })).not.toBeDisabled()
  })
})
