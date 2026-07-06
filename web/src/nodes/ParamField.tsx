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
    return (
      <div className="param-row nodrag nopan">
        {label}
        <input
          type="number"
          value={value == null ? '' : (value as number)}
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
    const selected = new Set((value as string[] | null) ?? [])
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

  return (
    <div className="param-row nodrag nopan">
      {label}
      <input
        type="text"
        value={(value as string | null) ?? ''}
        onChange={(e) => onChange(e.target.value || null)}
      />
    </div>
  )
}
