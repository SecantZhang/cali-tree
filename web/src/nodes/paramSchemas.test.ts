import { describe, expect, it } from 'vitest'
import { defaultParamsFor } from './paramSchemas'

describe('Rubric-Lite parameter schema', () => {
  it('defaults cutpoint validation to task grouping', () => {
    expect(defaultParamsFor('rubric_lite_fit')).toMatchObject({
      group_by_task: true,
    })
  })
})
