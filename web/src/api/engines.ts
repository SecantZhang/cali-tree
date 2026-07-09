import { api } from './client'

export interface EndpointHealth {
  url: string
  ok: boolean
  status: number | null
  latency: number
  error: string | null
}

export interface EngineHealthCheckResult {
  endpoints: EndpointHealth[]
}

// Probes the LM gateway endpoints for the LM Engine Node's "Test this engine" button. This
// makes a real (billable) gateway call per endpoint, so `allowLive` must be true (the caller
// confirms first) — the backend refuses with a 400 otherwise. See routes/engines.py.
export function checkEngineHealth(
  engineKind: string, model: string | null, allowLive: boolean,
): Promise<EngineHealthCheckResult> {
  return api.post('/api/engines/health-check', {
    engine_kind: engineKind,
    model: model || null,
    allow_live: allowLive,
  })
}
