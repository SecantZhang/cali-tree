import { expect, test } from '@playwright/test'
import { waitForPaletteLoaded } from '../helpers'

test.describe('manual credentials', () => {
  test('saving and clearing credentials round-trips through the real backend', async ({
    page,
  }) => {
    await page.goto('/')
    await waitForPaletteLoaded(page)

    // global-setup.ts always sets CHAT_GPT_API_KEY/OPENAI_COMPAT_BASE_URL (pointed at the
    // mock gateway) for this backend process, so the baseline is "environment variables",
    // not "not configured" — this test proves the manual override takes precedence over
    // that, and that clearing it correctly falls back to those env vars, not to "none".
    //
    // API Key lives inside the Settings dropdown (SettingsMenu.tsx) — opened once here and
    // never explicitly closed; the Credentials modal is nested inside it, so closing that
    // modal reveals the dropdown still open underneath for the second round below.
    await page.getByTitle('Settings').click()
    const credentialsButton = page.getByTitle('API credentials')
    await expect(credentialsButton.locator('.status-dot')).toHaveClass(/status-done/)

    await credentialsButton.click()
    const modal = page.locator('.modal-panel')
    await expect(modal).toBeVisible()
    await expect(modal.getByText('Currently using: environment variables')).toBeVisible()

    await modal.getByPlaceholder('sk-...').fill('sk-e2e-manual-token')
    await modal.getByPlaceholder('https://...').fill('https://manual.e2e.example.com/')
    await modal.getByRole('button', { name: 'Save' }).click()

    await expect(modal.getByText('Currently using: a manually entered credential')).toBeVisible()
    await expect(modal.getByText('https://manual.e2e.example.com/')).toBeVisible()

    // Closing and reopening re-fetches status from the real backend — not just local state.
    await page.getByRole('button', { name: 'Close' }).click()
    await expect(modal).toHaveCount(0)
    await expect(credentialsButton.locator('.status-dot')).toHaveClass(/status-done/)

    await credentialsButton.click()
    await expect(modal.getByText('Currently using: a manually entered credential')).toBeVisible()

    await modal.getByRole('button', { name: 'Clear' }).click()
    await expect(modal.getByText('Currently using: environment variables')).toBeVisible()
    await page.getByRole('button', { name: 'Close' }).click()
    await expect(credentialsButton.locator('.status-dot')).toHaveClass(/status-done/)
  })
})
