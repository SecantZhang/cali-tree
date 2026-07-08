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
  const label = <label className="param-label">{name}</label>

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
    // Falls back to the schema default for display when the stored value is null/unset
    // (e.g. an older saved workflow that predates this param, or a field the user never
    // touched) — the executor applies the exact same fallback at run time, so showing it
    // here means the node always displays what will actually run, never a blank box.
    const display = value == null ? (field.default as number | null | undefined) : (value as number)
    return (
      <div className="param-row nodrag nopan">
        {label}
        <input
          type="number"
          value={display == null ? '' : display}
          min={field.min}
          max={field.max}
          onChange={(e) => onChange(e.target.value === '' ? null : Number(e.target.value))}
        />
      </div>
    )
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

  // Same schema-default fallback as the number field above, for the same reason.
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
