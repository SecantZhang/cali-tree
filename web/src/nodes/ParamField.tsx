import { useState } from 'react'
import type { ParamField as ParamFieldSchema } from './paramSchemas'

// Shared by Inspector.tsx (right panel) and the inline node body (canvas) — one widget
// implementation, one place params actually get written (updateNodeParams), so editing
// on the canvas and editing in the Inspector are the same code path.
//
// `nodrag nopan` are required on every interactive control: without them, React Flow
// treats clicks/drags inside the node as canvas panning or node dragging instead of
// interacting with the input.
export function ParamField({
  name, field, value, onChange,
}: {
  name: string
  field: ParamFieldSchema
  value: unknown
  onChange: (v: unknown) => void
}) {
  const label = <label className="param-label" title={name}>{name}</label>

  if (field.type === 'bool') {
    return (
      <div className="param-row nodrag nopan">
        {label}
        <input
          type="checkbox" checked={Boolean(value)}
          onChange={(e) => onChange(e.target.checked)}
        />
      </div>
    )
  }

  if (field.type === 'number') {
    return <NumberParamField name={name} field={field} value={value} onChange={onChange} />
  }

  if (field.type === 'enum') {
    return (
      <div className="param-row nodrag nopan">
        {label}
        <select value={(value as string) ?? ''} onChange={(e) => onChange(e.target.value || null)}>
          <option value="">(default)</option>
          {field.options?.map((opt) => (
            <option key={opt} value={opt}>{opt}</option>
          ))}
        </select>
      </div>
    )
  }

  if (field.type === 'list[enum]') {
    // A null/empty selection means "every option" at run time for every list[enum] param
    // that currently exists (e.g. an unset `metrics` runs every judge of that modality) —
    // so an unset value displays as every box checked, not none, for the same
    // "show what will actually run" reason as the number/string fallback above.
    const selected = value == null ? new Set(field.options ?? []) : new Set(value as string[])
    return (
      <div className="param-row param-row-list nodrag nopan">
        {label}
        <div className="checkbox-list">
          {field.options?.map((opt) => (
            <label key={opt} className="checkbox-list-item">
              <input
                type="checkbox"
                checked={selected.has(opt)}
                onChange={(e) => {
                  const next = new Set(selected)
                  if (e.target.checked) next.add(opt)
                  else next.delete(opt)
                  onChange(next.size ? Array.from(next) : null)
                }}
              />
              {opt}
            </label>
          ))}
        </div>
      </div>
    )
  }

  if (field.type === 'list[string]') {
    return (
      <div className="param-row nodrag nopan">
        {label}
        <input
          type="text"
          placeholder="comma,separated"
          value={((value as string[] | null) ?? []).join(',')}
          onChange={(e) => {
            const parts = e.target.value.split(',').map((s) => s.trim()).filter(Boolean)
            onChange(parts.length ? parts : null)
          }}
        />
      </div>
    )
  }

  // Falls back to the schema default for display when the stored value is null/unset
  // (e.g. an older saved workflow that predates this param) — shows what will actually run.
  const display = (value as string | null | undefined) ?? (field.default as string | null | undefined) ?? ''
  return (
    <div className="param-row nodrag nopan">
      {label}
      <input
        type="text"
        value={display}
        onChange={(e) => onChange(e.target.value || null)}
      />
    </div>
  )
}

// Split out from ParamField so its local typing state is an unconditional hook call for
// this component's own lifetime, not one nested inside a branch of a bigger function.
//
// A plain `value={committedNumber}` (the old approach) fights the user while typing: the
// browser's native number-parsing coerces every intermediate string (an empty field, a
// trailing "-" or ".") into a committed number on every keystroke, which then gets fed
// right back into the controlled `value`, snapping the visible text back to whatever that
// coercion produced (e.g. clearing the field re-shows the schema default the instant you
// finish deleting; typing "0." collapses back to "0", deleting the "." you just typed).
//
// Instead, `raw` is the single source of truth for what's *displayed*, decoupled from the
// committed store value except at mount — the store is only ever written when `raw` is
// currently a real, finite number (never on an empty/incomplete string), and is only ever
// used to *restore* `raw` on blur if what's left behind doesn't parse.
//
// Deliberately `type="text"`, not `type="number"`: a native number input sanitizes its own
// `value` to `""` the instant the current text isn't a complete, valid number (confirmed —
// this is what broke a trailing "0." in this exact fix's own test), which defeats holding
// `raw` as a mid-typing string at all. `inputMode="decimal"` keeps the numeric keyboard on
// mobile without that sanitization; `min`/`max`/`step` are schema metadata only here, no
// longer native HTML attributes, since the user chose "revert on blur", not "clamp".
function NumberParamField({
  name, field, value, onChange,
}: {
  name: string
  field: ParamFieldSchema
  value: unknown
  onChange: (v: unknown) => void
}) {
  const committed = value == null ? (field.default as number | null | undefined) : (value as number)
  const [raw, setRaw] = useState<string>(() => (committed == null ? '' : String(committed)))

  return (
    <div className="param-row nodrag nopan">
      <label className="param-label" title={name}>{name}</label>
      <input
        type="text"
        inputMode="decimal"
        value={raw}
        onChange={(e) => {
          const next = e.target.value
          setRaw(next)
          const parsed = Number(next)
          // `Number('')` is 0 (not NaN) — must check for a genuinely empty/incomplete
          // string separately, or clearing the field would immediately commit 0.
          if (next.trim() !== '' && Number.isFinite(parsed)) {
            onChange(parsed)
          }
        }}
        onBlur={() => {
          const parsed = Number(raw)
          if (raw.trim() === '' || !Number.isFinite(parsed)) {
            setRaw(committed == null ? '' : String(committed))
          }
        }}
      />
    </div>
  )
}
