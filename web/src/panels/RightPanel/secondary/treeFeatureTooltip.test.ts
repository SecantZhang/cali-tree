import { describe, expect, it } from 'vitest'
import { treeFeatureTooltip } from './treeFeatureTooltip'

const BANK = [{ question: 'Over-penalizes a flaw?', raises_score_when: 'no' }]

describe('treeFeatureTooltip', () => {
  it('looks up qN features in the mined bank (CART tree)', () => {
    const tip = treeFeatureTooltip(BANK)
    expect(tip('q1')).toContain('Over-penalizes a flaw?')
    expect(tip('base_score')).toContain('1–5 score')
    expect(tip('q9')).toBeUndefined()
  })

  it('prefers the feature_labels map when present (semantic tree)', () => {
    const tip = treeFeatureTooltip(BANK, {
      'fm:audio_neglect': 'cited: ignore the audio track',
      base_score: 'the judge score',
    })
    expect(tip('fm:audio_neglect')).toBe('cited: ignore the audio track')
    // A labeled feature name that isn't a qN still resolves via the map.
    expect(tip('base_score')).toBe('the judge score')
    // Falls back to the bank when a feature has no label entry.
    expect(tip('q1')).toContain('Over-penalizes a flaw?')
  })
})
