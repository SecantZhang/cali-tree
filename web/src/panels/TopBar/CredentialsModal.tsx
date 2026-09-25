import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { ApiError } from '../../api/client'
import type { ApiProvider } from '../../api/settings'
import { clearCredentials, fetchCredentialsStatus, saveCredentials } from '../../api/settings'

const SOURCE_LABEL: Record<string, string> = {
  manual: 'a manually entered credential',
  env: 'environment variables',
  file: '.env-raw',
  none: 'nothing — not configured',
}

export function CredentialsModal({ open, onClose }: { open: boolean; onClose: () => void }) {
  const queryClient = useQueryClient()
  const [provider, setProvider] = useState<ApiProvider>('openai')
  const { data: status } = useQuery({
    queryKey: ['credentialsStatus', provider],
    queryFn: () => fetchCredentialsStatus(provider),
    enabled: open,
  })
  const [token, setToken] = useState('')
  const [baseUrl, setBaseUrl] = useState('')
  const [showToken, setShowToken] = useState(false)

  const saveMutation = useMutation({
    mutationFn: () => saveCredentials(token, baseUrl, undefined, provider),
    onSuccess: () => {
      setToken('')
      queryClient.invalidateQueries({ queryKey: ['credentialsStatus'] })
    },
  })
  const clearMutation = useMutation({
    mutationFn: () => clearCredentials(provider),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['credentialsStatus'] }),
  })

  if (!open) return null

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-panel modal-panel-small" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <strong>API Credentials</strong>
          <button onClick={onClose}>Close</button>
        </div>
        <div className="modal-body credentials-body">
          <div className="param-row">
            <label className="param-label" htmlFor="api-provider">Provider</label>
            <select id="api-provider" value={provider} disabled={saveMutation.isPending || clearMutation.isPending}
              onChange={(e) => { setProvider(e.target.value as ApiProvider); setToken(''); setBaseUrl(''); setShowToken(false); saveMutation.reset() }}>
              <option value="openai">OpenAI</option>
              <option value="gemini">Google Gemini</option>
            </select>
          </div>
          <p className="empty-hint">
            Currently using: {status ? SOURCE_LABEL[status.source] : '…'}
            {status?.base_url ? ` (${status.base_url})` : ''}
          </p>
          <p className="empty-hint">
            Saved to a local file on this machine (gitignored, never committed) and read by
            the backend only for calls to the selected provider. Keys are never returned to the browser.
          </p>

          <div className="param-row">
            <label className="param-label">API token</label>
            <div className="credentials-token-row">
              <input
                type={showToken ? 'text' : 'password'}
                value={token}
                onChange={(e) => setToken(e.target.value)}
                placeholder="sk-..."
              />
              <button type="button" onClick={() => setShowToken((s) => !s)}>
                {showToken ? 'Hide' : 'Show'}
              </button>
            </div>
          </div>

          <div className="param-row">
            <label className="param-label">Base URL</label>
            <input
              type="text"
              value={baseUrl}
              onChange={(e) => setBaseUrl(e.target.value)}
              placeholder="https://..."
            />
          </div>

          <p className="empty-hint">
            Leave Base URL blank to use {provider === 'openai' ? 'https://api.openai.com/v1' : 'https://generativelanguage.googleapis.com/v1beta'}.
            {' '}Save a separate key for each provider. Existing proxy settings are ignored by default.
          </p>

          {saveMutation.isError && (
            <p className="rationale-error">
              {saveMutation.error instanceof ApiError
                ? saveMutation.error.message
                : 'Failed to save credentials.'}
            </p>
          )}

          <div className="credentials-actions">
            <button
              className="btn-primary"
              disabled={!token.trim() || saveMutation.isPending}
              onClick={() => saveMutation.mutate()}
            >
              Save
            </button>
            <button
              disabled={status?.source !== 'manual' || clearMutation.isPending}
              onClick={() => clearMutation.mutate()}
            >
              Clear
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
