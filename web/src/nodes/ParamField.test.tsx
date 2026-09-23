import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { ParamField } from './ParamField'
import type { ParamField as ParamFieldSchema } from './paramSchemas'

const samplingRatioField: ParamFieldSchema = { type: 'number', default: 1.0, min: 0, max: 1, step: 0.05 }

describe('ParamField number input', () => {
  it('lets the field go empty while typing instead of snapping back to the default', () => {
    render(<ParamField name="sampling_ratio" field={samplingRatioField} value={1} onChange={vi.fn()} />)
    const input = screen.getByRole('textbox') as HTMLInputElement

    fireEvent.change(input, { target: { value: '' } })
    // Clearing the field must not be immediately overwritten by the schema default —
    // this is the exact "can't delete the leading digit" bug being fixed.
    expect(input.value).toBe('')
  })

  it('preserves a trailing decimal point while typing (e.g. "0." on the way to "0.05")', () => {
    render(<ParamField name="sampling_ratio" field={samplingRatioField} value={1} onChange={vi.fn()} />)
    const input = screen.getByRole('textbox') as HTMLInputElement

    fireEvent.change(input, { target: { value: '0.' } })
    expect(input.value).toBe('0.')

    fireEvent.change(input, { target: { value: '0.05' } })
    expect(input.value).toBe('0.05')
  })

  it('commits a value live once it parses to a finite number', () => {
    const onChange = vi.fn()
    render(<ParamField name="sampling_ratio" field={samplingRatioField} value={1} onChange={onChange} />)
    const input = screen.getByRole('textbox') as HTMLInputElement

    fireEvent.change(input, { target: { value: '0.05' } })
    expect(onChange).toHaveBeenCalledWith(0.05)
  })

  it('reverts to the last valid committed value on blur when left empty', () => {
    const onChange = vi.fn()
    render(<ParamField name="sampling_ratio" field={samplingRatioField} value={0.3} onChange={onChange} />)
    const input = screen.getByRole('textbox') as HTMLInputElement

    fireEvent.change(input, { target: { value: '' } })
    expect(input.value).toBe('')
    fireEvent.blur(input)
    // Reverts to the last committed value (0.3), not the schema default (1.0) and not left
    // blank — onChange is never called with an invalid/empty value in the first place.
    expect(input.value).toBe('0.3')
    expect(onChange).not.toHaveBeenCalled()
  })

  it('reverts to the schema default on blur when the field was never set', () => {
    render(<ParamField name="sampling_ratio" field={samplingRatioField} value={null} onChange={vi.fn()} />)
    const input = screen.getByRole('textbox') as HTMLInputElement

    fireEvent.change(input, { target: { value: '' } })
    fireEvent.blur(input)
    expect(input.value).toBe('1')
  })
})
