import { describe, expect, it } from 'vitest'
import { isValidSocketConnection } from './socketTypes'

describe('isValidSocketConnection', () => {
  it('accepts a matching raw_dataset source -> dataset connection', () => {
    expect(isValidSocketConnection('peanut_source', 'raw_dataset', 'dataset', 'raw_dataset')).toBe(true)
  })

  it('accepts a matching samples -> judge_text connection', () => {
    expect(isValidSocketConnection('dataset', 'samples', 'judge_text', 'samples')).toBe(true)
  })

  it('accepts a matching judge_text -> eval_text connection', () => {
    expect(isValidSocketConnection('judge_text', 'judge_result', 'eval_text', 'judge_result')).toBe(true)
  })

  it('accepts a matching judge_video -> eval_video connection', () => {
    expect(isValidSocketConnection('judge_video', 'judge_result', 'eval_video', 'judge_result')).toBe(true)
  })

  it('accepts a matching dataset labels -> eval_text/eval_video connection', () => {
    expect(isValidSocketConnection('dataset', 'labels', 'eval_text', 'labels')).toBe(true)
    expect(isValidSocketConnection('dataset', 'labels', 'eval_video', 'labels')).toBe(true)
  })

  it('accepts a matching lm_engine -> judge_text/judge_video engine_config connection', () => {
    expect(isValidSocketConnection('lm_engine', 'engine_config', 'judge_text', 'engine_config')).toBe(true)
    expect(isValidSocketConnection('lm_engine', 'engine_config', 'judge_video', 'engine_config')).toBe(true)
  })

  it('rejects wiring engine_config into a samples socket (type mismatch)', () => {
    expect(isValidSocketConnection('lm_engine', 'engine_config', 'judge_text', 'samples')).toBe(false)
  })

  it('rejects wiring a raw_dataset source directly into a Judge node (must pass through Dataset)', () => {
    expect(isValidSocketConnection('peanut_source', 'raw_dataset', 'judge_text', 'samples')).toBe(false)
  })

  it('rejects a type mismatch (samples socket into a labels socket)', () => {
    expect(isValidSocketConnection('dataset', 'samples', 'eval_text', 'labels')).toBe(false)
  })

  it('rejects an unknown source or target node type', () => {
    expect(isValidSocketConnection('nope', 'samples', 'judge_text', 'samples')).toBe(false)
    expect(isValidSocketConnection('dataset', 'samples', 'nope', 'samples')).toBe(false)
  })

  it('rejects a missing handle', () => {
    expect(isValidSocketConnection('dataset', null, 'judge_text', 'samples')).toBe(false)
    expect(isValidSocketConnection('dataset', 'samples', 'judge_text', undefined)).toBe(false)
  })

  it('rejects an unknown socket name on an otherwise valid node type', () => {
    expect(isValidSocketConnection('dataset', 'not_a_socket', 'judge_text', 'samples')).toBe(false)
  })
})
