import { api } from './client'

export interface CredentialsStatus {
  configured: boolean
  source: 'manual' | 'env' | 'file' | 'none'
  base_url: string | null
}

export function fetchCredentialsStatus(): Promise<CredentialsStatus> {
  return api.get('/api/settings/credentials')
}

export function saveCredentials(
  token: string,
  baseUrl: string,
  mirrorUrl?: string,
): Promise<CredentialsStatus> {
  return api.post('/api/settings/credentials', {
    token,
    base_url: baseUrl,
    mirror_url: mirrorUrl || undefined,
  })
}

export function clearCredentials(): Promise<CredentialsStatus> {
  return api.delete('/api/settings/credentials')
}
