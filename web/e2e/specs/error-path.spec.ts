import { expect, test } from '@playwright/test'
import { addNode, waitForPaletteLoaded } from '../helpers'

// addNode's module-level id counter (graphStore.ts) resets on every fresh page load.
const JUDGE = 'judge_text-1'

test.describe('error path', () => {
  test('a Judge Node with no dataset input wired fails with the real backend error message', async ({
    page,
  }) => {
    await page.goto('/')
    await waitForPaletteLoaded(page)

    await addNode(page, 'judge_text')
    const judgeNode = page.getByTestId(`rf__node-${JUDGE}`)
    await expect(judgeNode).toBeVisible()

    // No connections at all — the Judge Node's `samples` input is left unwired.
    await expect(page.locator('.react-flow__edge')).toHaveCount(0)

    const runButton = page.getByRole('button', { name: /^Run(ning…)?$/ })
    await runButton.click()

    await expect(runButton).toHaveText('Run', { timeout: 10000 })

    const statusDot = judgeNode.locator('.status-dot')
    await expect(statusDot).toHaveClass(/status-error/)
    await expect(statusDot).toHaveAttribute(
      'title',
      "Text Judge Node requires a 'samples' input (wire a Dataset Node's `samples` output)",
    )

    // The top-level run error banner (.console-error) only carries graph-level failures
    // (e.g. a malformed graph) — a single node's own failure surfaces on that node's
    // status dot (checked above), not here, so the overall run status is all this proves.
    await expect(page.locator('.console-header')).toContainText('Run status: error')
  })
})
