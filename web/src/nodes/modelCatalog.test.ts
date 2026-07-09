import { describe, expect, it } from 'vitest'
import { MODELS_BY_ENGINE_KIND, modelsFor } from './modelCatalog'

describe('modelCatalog', () => {
  it('covers all 7 provider families', () => {
    expect(Object.keys(MODELS_BY_ENGINE_KIND).sort()).toEqual(
      ['claude', 'deepseek', 'gemini', 'gpt', 'kimi', 'llama', 'qwen'].sort(),
    )
  })

  it('every family has at least one model', () => {
    for (const models of Object.values(MODELS_BY_ENGINE_KIND)) {
      expect(models.length).toBeGreaterThan(0)
    }
  })

  it('modelsFor returns the matching family list', () => {
    expect(modelsFor('claude')).toEqual(MODELS_BY_ENGINE_KIND.claude)
  })

  it('modelsFor returns an empty array for an unknown kind', () => {
    expect(modelsFor('not-a-real-kind')).toEqual([])
  })
})
