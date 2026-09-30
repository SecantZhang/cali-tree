import { describe, expect, it } from 'vitest'
import { NODE_PARAM_SCHEMAS, defaultParamsFor } from './paramSchemas'

describe('Modular CaliTree parameters', () => {
  it('preserves legacy defaults and exposes selectable strategies', () => {
    expect(defaultParamsFor('calitree_train')).toMatchObject({
      modular_mode: false, optimizer_plan: 'textgrad', decomposition_strategy: 'two_way',
      merge_strategy: 'prompt_synthesis', max_merge_children: 2, gepa_python: '',
    })
    expect(NODE_PARAM_SCHEMAS.calitree_train.optimizer_plan.options).toEqual([
      'textgrad', 'gepa', 'textgrad_then_gepa', 'gepa_then_textgrad', 'best_of_both', 'evaluate_only',
    ])
    expect(NODE_PARAM_SCHEMAS.calitree_train.decomposition_strategy.options)
      .toEqual(['two_way', 'two_way_vision'])
    expect(NODE_PARAM_SCHEMAS.calitree_train.merge_strategy.options)
      .toEqual(['prompt_synthesis', 'concatenate'])
  })
})

describe('Rubric-Lite parameter schema', () => {
  it('defaults cutpoint validation to task grouping', () => {
    expect(defaultParamsFor('rubric_lite_fit')).toMatchObject({
      group_by_task: true,
    })
  })

  it('registers the experimental evidence-ledger prompt and artifact', () => {
    expect(NODE_PARAM_SCHEMAS.rubric_lite_train.rubric_version.options)
      .toContain('rubric_lite_v6')
    expect(NODE_PARAM_SCHEMAS.rubric_lite_frozen.model_version.options)
      .toContain('rubric_lite_v6_evidence_ledger_experimental')
  })
})
