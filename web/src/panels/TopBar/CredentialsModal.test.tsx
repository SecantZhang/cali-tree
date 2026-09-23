import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { CredentialsModal } from './CredentialsModal'

let statusResponse: unknown = { configured: false, source: 'none', base_url: null }
let lastPostBody: unknown = null
let deleteCalled = false

function mockJsonFor(url: string, init?: RequestInit): unknown {
  if (url.endsWith('/api/settings/credentials')) {
    if (init?.method === 'POST') {
      lastPostBody = JSON.parse(init.body as string)
      statusResponse = { configured: true, source: 'manual', base_url: lastPostBody && (lastPostBody as { base_url: string }).base_url }
      return statusResponse
    }
    if (init?.method === 'DELETE') {
      deleteCalled = true
      statusResponse = { configured: false, source: 'none', base_url: null }
      return statusResponse
    }
    return statusResponse
  }
  return {}
}

beforeEach(() => {
  statusResponse = { configured: false, source: 'none', base_url: null }
  lastPostBody = null
  deleteCalled = false
  vi.stubGlobal(
    'fetch',
    vi.fn(async (url: string, init?: RequestInit) => ({
      ok: true,
      status: 200,
      json: async () => mockJsonFor(url, init),
    })),
  )
})

afterEach(() => {
  vi.unstubAllGlobals()
})

function renderModal(onClose = vi.fn()) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return {
    onClose,
    ...render(
      <QueryClientProvider client={queryClient}>
        <CredentialsModal open onClose={onClose} />
      </QueryClientProvider>,
    ),
  }
}

describe('CredentialsModal', () => {
  it('renders nothing when closed', () => {
    const queryClient = new QueryClient()
    render(
      <QueryClientProvider client={queryClient}>
        <CredentialsModal open={false} onClose={vi.fn()} />
      </QueryClientProvider>,
    )
    expect(screen.queryByText('API Credentials')).toBeNull()
  })

  it('shows "not configured" status when nothing is set', async () => {
    renderModal()
    expect(await screen.findByText(/Currently using: nothing/)).toBeInTheDocument()
  })

  it('filling the form and saving posts the right body and updates the status', async () => {
    renderModal()
    await screen.findByText(/Currently using: nothing/)

    fireEvent.change(screen.getByPlaceholderText('sk-...'), {
      target: { value: 'sk-test-token' },
    })
    fireEvent.change(screen.getByPlaceholderText('https://...'), {
      target: { value: 'https://gateway.example.com/' },
    })
    fireEvent.click(screen.getByRole('button', { name: 'Save' }))

    await screen.findByText(/Currently using: a manually entered credential/)
    expect(lastPostBody).toEqual({
      token: 'sk-test-token',
      base_url: 'https://gateway.example.com/',
      mirror_url: undefined,
    })
  })

  it('the token input is masked by default and can be revealed', () => {
    renderModal()
    const input = screen.getByPlaceholderText('sk-...') as HTMLInputElement
    expect(input.type).toBe('password')
    fireEvent.click(screen.getByRole('button', { name: 'Show' }))
    expect(input.type).toBe('text')
  })

  it('Save stays disabled until both token and base URL are filled in', () => {
    renderModal()
    const saveButton = screen.getByRole('button', { name: 'Save' })
    expect(saveButton).toBeDisabled()

    fireEvent.change(screen.getByPlaceholderText('sk-...'), { target: { value: 'sk-x' } })
    expect(saveButton).toBeDisabled()

    fireEvent.change(screen.getByPlaceholderText('https://...'), {
      target: { value: 'https://gateway.example.com/' },
    })
    expect(saveButton).not.toBeDisabled()
  })

  it('Clear is disabled unless the current source is manual, and calls DELETE when clicked', async () => {
    statusResponse = {
      configured: true, source: 'manual', base_url: 'https://gateway.example.com/',
    }
    renderModal()
    await screen.findByText(/Currently using: a manually entered credential/)
    const clearButton = screen.getByRole('button', { name: 'Clear' })
    expect(clearButton).not.toBeDisabled()

    fireEvent.click(clearButton)
    await screen.findByText(/Currently using: nothing/)
    expect(deleteCalled).toBe(true)
  })

  it('Clear is disabled when the current source is env, not manual', async () => {
    statusResponse = { configured: true, source: 'env', base_url: 'https://env.example.com/' }
    renderModal()
    await screen.findByText(/Currently using: environment variables/)
    expect(screen.getByRole('button', { name: 'Clear' })).toBeDisabled()
  })

  it('clicking Close calls onClose', async () => {
    const { onClose } = renderModal()
    fireEvent.click(screen.getByRole('button', { name: 'Close' }))
    expect(onClose).toHaveBeenCalled()
  })
})
