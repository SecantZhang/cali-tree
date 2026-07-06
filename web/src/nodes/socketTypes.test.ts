import { describe, expect, it } from 'vitest'
import { isValidSocketConnection } from './socketTypes'

describe('isValidSocketConnection', () => {
  it('accepts a matching dataset -> judge connection', () => {
    expect(isValidSocketConnection('dataset', 'dataset', 'judge', 'dataset')).toBe(true)
  })

  it('accepts a matching judge -> eval connection', () => {
    expect(isValidSocketConnection('judge', 'judge_result', 'eval', 'judge_result')).toBe(true)
  })

  it('accepts a matching dataset(labels) -> eval connection', () => {
    expect(isValidSocketConnection('dataset', 'labels', 'eval', 'labels')).toBe(true)
  })

  it('rejects a type mismatch (dataset socket into a labels socket)', () => {
    expect(isValidSocketConnection('dataset', 'dataset', 'eval', 'labels')).toBe(false)
  })

  it('rejects an unknown source or target node type', () => {
    expect(isValidSocketConnection('nope', 'dataset', 'judge', 'dataset')).toBe(false)
    expect(isValidSocketConnection('dataset', 'dataset', 'nope', 'dataset')).toBe(false)
  })

  it('rejects a missing handle', () => {
    expect(isValidSocketConnection('dataset', null, 'judge', 'dataset')).toBe(false)
    expect(isValidSocketConnection('dataset', 'dataset', 'judge', undefined)).toBe(false)
  })

  it('rejects an unknown socket name on an otherwise valid node type', () => {
    expect(isValidSocketConnection('dataset', 'not_a_socket', 'judge', 'dataset')).toBe(false)
  })
})
