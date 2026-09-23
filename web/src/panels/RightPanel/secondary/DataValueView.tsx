// Shared value renderer for the generic Inputs/Outputs tabs. Node socket payloads can be
// tiny (a scalar) or huge (a 1,170-item raw_dataset, base64 video, debate transcripts), so
// this NEVER dumps a value whole: it shows a one-line summary sized to the value's shape,
// with an expandable (collapsed-by-default) pretty-print that is itself length-capped.

const MAX_JSON_CHARS = 20000
const MAX_STRING_PREVIEW = 800

export function summarize(value: unknown): string {
  if (value === null || value === undefined) return '—'
  if (typeof value === 'string') {
    if (/^data:|^[A-Za-z0-9+/]{200,}={0,2}$/.test(value)) return `base64/data (${value.length} chars)`
    return `string (${value.length} chars)`
  }
  if (typeof value === 'number' || typeof value === 'boolean') return String(value)
  if (Array.isArray(value)) return `list · ${value.length} item${value.length === 1 ? '' : 's'}`
  if (typeof value === 'object') {
    const keys = Object.keys(value as Record<string, unknown>)
    const sample = keys.slice(0, 4).join(', ')
    return `object · ${keys.length} key${keys.length === 1 ? '' : 's'}${sample ? ` (${sample}${keys.length > 4 ? ', …' : ''})` : ''}`
  }
  return String(value)
}

function preview(value: unknown): string {
  if (typeof value === 'string') {
    return value.length > MAX_STRING_PREVIEW
      ? value.slice(0, MAX_STRING_PREVIEW) + `\n… (+${value.length - MAX_STRING_PREVIEW} chars)`
      : value
  }
  let json: string
  try {
    json = JSON.stringify(value, null, 2)
  } catch {
    json = String(value)
  }
  if (json.length > MAX_JSON_CHARS) {
    return json.slice(0, MAX_JSON_CHARS) + `\n… (truncated, +${json.length - MAX_JSON_CHARS} chars)`
  }
  return json
}

export function DataValueView({ value }: { value: unknown }) {
  const scalar =
    value === null ||
    value === undefined ||
    typeof value === 'number' ||
    typeof value === 'boolean'
  if (scalar) {
    return <code className="data-value-scalar">{value === null || value === undefined ? '—' : String(value)}</code>
  }
  return (
    <details className="data-value">
      <summary>{summarize(value)}</summary>
      <pre className="json-preview">{preview(value)}</pre>
    </details>
  )
}
