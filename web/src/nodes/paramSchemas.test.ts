import { describe, expect, it } from 'vitest'
import { NODE_PARAM_SCHEMAS, defaultParamsFor } from './paramSchemas'

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
