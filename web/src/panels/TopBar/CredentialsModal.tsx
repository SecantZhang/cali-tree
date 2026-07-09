import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { ApiError } from '../../api/client'
import { clearCredentials, fetchCredentialsStatus, saveCredentials } from '../../api/settings'

const SOURCE_LABEL: Record<string, string> = {
  manual: 'a manually entered credential',
  env: 'environment variables',
  file: '.env-raw',
  none: 'nothing — not configured',
}

export function CredentialsModal({ open, onClose }: { open: boolean; onClose: () => void }) {
  const queryClient = useQueryClient()
  const { data: status } = useQuery({
    queryKey: ['credentialsStatus'],
    queryFn: fetchCredentialsStatus,
    enabled: open,
  })
  const [token, setToken] = useState('')
  const [baseUrl, setBaseUrl] = useState('')
  const [mirrorUrl, setMirrorUrl] = useState('')
  const [showToken, setShowToken] = useState(false)
  const [showAdvanced, setShowAdvanced] = useState(false)

  const saveMutation = useMutation({
    mutationFn: () => saveCredentials(token, baseUrl, mirrorUrl || undefined),
    onSuccess: () => {
      setToken('')
      queryClient.invalidateQueries({ queryKey: ['credentialsStatus'] })
    },
  })
  const clearMutation = useMutation({
    mutationFn: clearCredentials,
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
          <p className="empty-hint">
            Currently using: {status ? SOURCE_LABEL[status.source] : '…'}
            {status?.base_url ? ` (${status.base_url})` : ''}
          </p>
          <p className="empty-hint">
            Saved to a local file on this machine (gitignored, never committed) and read by
            the backend for every Judge Node call — never sent anywhere else.
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

          {!showAdvanced && (
            <button type="button" onClick={() => setShowAdvanced(true)}>
              Advanced (mirror URL)
            </button>
          )}
          {showAdvanced && (
            <div className="param-row">
              <label className="param-label">Mirror URL (optional)</label>
              <input
                type="text"
                value={mirrorUrl}
                onChange={(e) => setMirrorUrl(e.target.value)}
                placeholder="https://..."
              />
            </div>
          )}

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
              disabled={!token || !baseUrl || saveMutation.isPending}
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
