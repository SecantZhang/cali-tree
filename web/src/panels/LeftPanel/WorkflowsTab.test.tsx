import { describe, expect, it } from 'vitest'
import { buildWorkflowTree } from './workflowTree'

describe('buildWorkflowTree', () => {
  it('groups recursive workflow paths while retaining flat workflows', () => {
    const tree = buildWorkflowTree([
      'quick_eval',
      'examples/edit_aware_calibration',
      'research/v1/ablation',
      'research/v1/baseline',
    ])

    expect(tree.workflows).toEqual([{ label: 'quick_eval', path: 'quick_eval' }])
    expect(tree.folders.examples.workflows).toEqual([
      {
        label: 'edit_aware_calibration',
        path: 'examples/edit_aware_calibration',
      },
    ])
    expect(tree.folders.research.folders.v1.workflows).toEqual([
      { label: 'ablation', path: 'research/v1/ablation' },
      { label: 'baseline', path: 'research/v1/baseline' },
    ])
  })
})
