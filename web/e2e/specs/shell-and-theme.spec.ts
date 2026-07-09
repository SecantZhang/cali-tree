import { expect, test } from '@playwright/test'
import { paletteItem, waitForPaletteLoaded } from '../helpers'

test.describe('app shell and theme', () => {
  test('loads the 4-pane shell against the real backend', async ({ page }) => {
    await page.goto('/')

    await expect(page.getByText('VEJudge Interface')).toBeVisible()
    // The palette only shows real entries once GET /api/nodes has returned from the
    // real backend — proves the frontend build + backend + fixture wiring all work.
    await waitForPaletteLoaded(page)
    await expect(paletteItem(page, 'peanut_source')).toBeVisible()
    await expect(paletteItem(page, 'dataset')).toBeVisible()
    await expect(paletteItem(page, 'preprocessing')).toBeVisible()
    await expect(paletteItem(page, 'lm_engine')).toBeVisible()
    await expect(paletteItem(page, 'judge_text')).toBeVisible()
    await expect(paletteItem(page, 'judge_video')).toBeVisible()
    await expect(paletteItem(page, 'eval_text')).toBeVisible()
    await expect(paletteItem(page, 'eval_video')).toBeVisible()

    await expect(page.locator('.left-panel')).toBeVisible()
    await expect(page.locator('.canvas-area')).toBeVisible()
    await expect(page.locator('.right-panel')).toBeVisible()
    await expect(page.locator('.bottom-panel')).toBeVisible()
    await expect(page.getByText('Select a node to inspect its parameters.')).toBeVisible()
    await expect(page.getByText('Run a graph to see live logs here.')).toBeVisible()
  })

  test('toggling theme changes data-theme, the canvas colorMode, and real computed colors', async ({
    page,
  }) => {
    await page.goto('/')
    await waitForPaletteLoaded(page)

    const html = page.locator('html')
    const canvas = page.locator('.react-flow')
    const bodyBg = () => page.locator('body').evaluate((el) => getComputedStyle(el).backgroundColor)

    await expect(html).toHaveAttribute('data-theme', 'light')
    await expect(canvas).toHaveClass(/\blight\b/)
    expect(await bodyBg()).toBe('rgb(255, 255, 255)') // --bg in [data-theme='light']

    await page.screenshot({ path: 'e2e/screenshots/light-theme.png', fullPage: true })

    await page.getByTitle('Toggle theme').click()

    await expect(html).toHaveAttribute('data-theme', 'dark')
    await expect(canvas).toHaveClass(/\bdark\b/)
    await expect(canvas).not.toHaveClass(/\blight\b/)
    // A real browser actually recomputes styles from the stylesheet — jsdom (used by
    // the vitest suite) cannot see this at all, which is exactly the gap this E2E
    // suite exists to close.
    expect(await bodyBg()).toBe('rgb(22, 23, 29)') // --bg in [data-theme='dark']

    await page.screenshot({ path: 'e2e/screenshots/dark-theme.png', fullPage: true })

    // Toggling back returns to the original palette — the preference isn't one-way.
    await page.getByTitle('Toggle theme').click()
    await expect(html).toHaveAttribute('data-theme', 'light')
  })
})
