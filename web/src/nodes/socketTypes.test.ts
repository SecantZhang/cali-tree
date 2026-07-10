import { describe, expect, it } from 'vitest'
import { isValidSocketConnection } from './socketTypes'

describe('isValidSocketConnection', () => {
  it('accepts a matching raw_dataset source -> dataset connection', () => {
    expect(isValidSocketConnection('peanut_source', 'raw_dataset', 'dataset', 'raw_dataset')).toBe(true)
  })

  it('accepts a matching samples -> judge connection', () => {
    expect(isValidSocketConnection('dataset', 'samples', 'judge', 'samples')).toBe(true)
  })

  it('accepts a matching judge_prompt judge_spec -> judge connection', () => {
    expect(isValidSocketConnection('judge_prompt', 'judge_spec', 'judge', 'judge_spec')).toBe(true)
  })

  it('accepts a matching judge -> eval connection', () => {
    expect(isValidSocketConnection('judge', 'judge_result', 'eval', 'judge_result')).toBe(true)
  })

  it('accepts a matching dataset labels -> eval connection', () => {
    expect(isValidSocketConnection('dataset', 'labels', 'eval', 'labels')).toBe(true)
  })

  it('accepts a matching lm_engine -> judge engine_config connection', () => {
    expect(isValidSocketConnection('lm_engine', 'engine_config', 'judge', 'engine_config')).toBe(true)
  })

  it('rejects wiring engine_config into a samples socket (type mismatch)', () => {
    expect(isValidSocketConnection('lm_engine', 'engine_config', 'judge', 'samples')).toBe(false)
  })

  it('rejects wiring a judge_spec into a samples socket (type mismatch)', () => {
    expect(isValidSocketConnection('judge_prompt', 'judge_spec', 'judge', 'samples')).toBe(false)
  })

  it('rejects wiring a raw_dataset source directly into a Judge node (must pass through Dataset)', () => {
    expect(isValidSocketConnection('peanut_source', 'raw_dataset', 'judge', 'samples')).toBe(false)
  })

  it('rejects a type mismatch (samples socket into a labels socket)', () => {
    expect(isValidSocketConnection('dataset', 'samples', 'eval', 'labels')).toBe(false)
  })

  it('rejects an unknown source or target node type', () => {
    expect(isValidSocketConnection('nope', 'samples', 'judge', 'samples')).toBe(false)
    expect(isValidSocketConnection('dataset', 'samples', 'nope', 'samples')).toBe(false)
  })

  it('rejects a missing handle', () => {
    expect(isValidSocketConnection('dataset', null, 'judge', 'samples')).toBe(false)
    expect(isValidSocketConnection('dataset', 'samples', 'judge', undefined)).toBe(false)
  })

  it('rejects an unknown socket name on an otherwise valid node type', () => {
    expect(isValidSocketConnection('dataset', 'not_a_socket', 'judge', 'samples')).toBe(false)
  })
})
