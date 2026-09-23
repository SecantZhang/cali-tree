import { api } from './client'

export function listLoaders(): Promise<string[]> {
  return api.get('/api/datasets/loaders')
}

export function listItems(
  loader: string, opts?: { model?: string; project?: string },
): Promise<{ items: string[] }> {
  const q = new URLSearchParams()
  if (opts?.model) q.set('model', opts.model)
  if (opts?.project) q.set('project', opts.project)
  const qs = q.toString()
  return api.get(`/api/datasets/${encodeURIComponent(loader)}/items${qs ? `?${qs}` : ''}`)
}

export function getItem(loader: string, itemId: string, model?: string): Promise<unknown> {
  const qs = model ? `?model=${encodeURIComponent(model)}` : ''
  return api.get(
    `/api/datasets/${encodeURIComponent(loader)}/items/${encodeURIComponent(itemId)}${qs}`,
  )
}
