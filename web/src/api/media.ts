// Builds a URL for GET /api/media (see vejudge/interface/server/routes/media.py) — a
// path-confined file stream, used for <video> playback in the Source/Eval secondary tabs.
// Not a JSON request through `api.get`, since the response body is the raw file, not JSON.

import { API_BASE } from './client'

export function mediaUrl(path: string): string {
  return `${API_BASE}/api/media?path=${encodeURIComponent(path)}`
}
