import { api } from './client'

export interface CredentialsStatus {
  configured: boolean
  source: 'manual' | 'env' | 'file' | 'none'
  base_url: string | null
}

export type ApiProvider = 'openai' | 'gemini'

const credentialPath = (provider: ApiProvider) => '/api/settings/credentials' + (provider === 'openai' ? '' : `?provider=${provider}`)

export function fetchCredentialsStatus(provider: ApiProvider = 'openai'): Promise<CredentialsStatus> {
  return api.get(credentialPath(provider))
}

export function saveCredentials(
  token: string,
  baseUrl: string,
  mirrorUrl?: string,
  provider: ApiProvider = 'openai',
): Promise<CredentialsStatus> {
  return api.post('/api/settings/credentials', {
    token,
    provider,
    base_url: baseUrl,
    mirror_url: mirrorUrl || undefined,
  })
}

export function clearCredentials(provider: ApiProvider = 'openai'): Promise<CredentialsStatus> {
  return api.delete(credentialPath(provider))
}
