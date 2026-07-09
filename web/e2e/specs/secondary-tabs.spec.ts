import { expect, test } from '@playwright/test'
import { addNode, dragConnect, waitForPaletteLoaded } from '../helpers'

// addNode's id counter resets each fresh page load, so the click order fixes these ids.
async function connect(
  page: import('@playwright/test').Page,
  sourceNodeId: string, sourceHandleId: string,
  targetNodeId: string, targetHandleId: string,
) {
  const source = page.locator(`[data-nodeid="${sourceNodeId}"][data-handleid="${sourceHandleId}"].source`)
  const target = page.locator(`[data-nodeid="${targetNodeId}"][data-handleid="${targetHandleId}"].target`)
  await dragConnect(page, source, target)
}

test.describe('secondary tabs', () => {
  test('the top-bar progress bars are visible in a flat idle state before any run', async ({ page }) => {
    await page.goto('/')
    await waitForPaletteLoaded(page)

    const runProgress = page.locator('.run-progress')
    await expect(runProgress).toBeVisible()
    await expect(runProgress.getByText('Workflow progress — Idle')).toBeVisible()
    await expect(runProgress.getByText('Idle — no run in progress')).toBeVisible()
    // Both bars are in the flat idle state (not the busy indeterminate animation).
    const idleFills = runProgress.locator('.progress-bar-fill.progress-bar-idle')
    await expect(idleFills).toHaveCount(2)
    // Both bars use the inline layout (label left, track right on one row) — and their
    // fixed-width label columns make the two tracks line up at the same left edge.
    const inlineBars = runProgress.locator('.progress-bar-inline')
    await expect(inlineBars).toHaveCount(2)
    const trackLefts = await inlineBars
      .locator('.progress-bar-track')
      .evaluateAll((els) => els.map((el) => el.getBoundingClientRect().left))
    expect(trackLefts).toHaveLength(2)
    expect(Math.abs(trackLefts[0] - trackLefts[1])).toBeLessThan(1)
  })

  test('the Dataset node secondary tab shows the schema reference and browses sampled items + labels', async ({ page }) => {
    await page.goto('/')
    await waitForPaletteLoaded(page)

    await addNode(page, 'peanut_source')
    await addNode(page, 'dataset')
    await page.getByRole('button', { name: 'Fit View' }).click()

    await connect(page, 'peanut_source-1', 'raw_dataset', 'dataset-2', 'raw_dataset')

    // A dry run is enough — the Dataset node samples the real fixture data (and joins human
    // labels) regardless of dry-run, which only gates the Judge nodes' gateway calls.
    const runButton = page.getByRole('button', { name: /^Run(ning…)?$/ })
    await runButton.click()
    await expect(runButton).toHaveText('Run', { timeout: 10000 })
    await expect(page.getByTestId('rf__node-dataset-2').locator('.status-dot.status-done')).toBeVisible()

    await page.getByTestId('rf__node-dataset-2').dblclick()
    const modal = page.locator('.modal-panel')
    await expect(modal).toBeVisible()

    // The static schema reference is always available; expanding it shows real field rows.
    const schema = modal.locator('.schema-details')
    await schema.locator('summary').click()
    await expect(schema.getByText('output.output_video_path')).toBeVisible()

    // The item browser lists this node's own sampled items; at least one carries a human
    // label (the fixture has annotations), flagged with a dot in the list.
    const items = modal.locator('.secondary-item-list li')
    await expect(items.first()).toBeVisible()
    const labeledItem = modal.locator('.secondary-item-list li', {
      has: page.locator('.item-has-label'),
    })
    await expect(labeledItem.first()).toBeVisible()

    // Selecting a labeled item renders its structured preview + the joined human-label block.
    await labeledItem.first().click()
    await expect(modal.locator('.item-preview h4')).toBeVisible()
    await expect(modal.locator('.human-label-block')).toBeVisible()

    await page.getByRole('button', { name: 'Close' }).click()
    await expect(modal).toHaveCount(0)
  })

  test('the LM Engine secondary tab shows config, feeds, and a real (mock) endpoint health check', async ({ page }) => {
    await page.goto('/')
    await waitForPaletteLoaded(page)

    await addNode(page, 'lm_engine')
    await addNode(page, 'judge_text')
    await page.getByRole('button', { name: 'Fit View' }).click()
    await connect(page, 'lm_engine-1', 'engine_config', 'judge_text-2', 'engine_config')

    await page.getByTestId('rf__node-lm_engine-1').dblclick()
    const modal = page.locator('.modal-panel')
    await expect(modal).toBeVisible()

    // Config summary + the "feeds" list traced off the live graph edge.
    await expect(modal.getByText('Engine kind:')).toBeVisible()
    await expect(modal.getByText('Text Judge')).toBeVisible()

    // "Test this engine" makes a real gateway call (to the local mock gateway, per
    // global-setup) after a confirm — auto-accept the dialog, then assert the endpoint
    // result row renders. The mock returns 200, so the endpoint reads as healthy.
    page.once('dialog', (dialog) => dialog.accept())
    await modal.getByRole('button', { name: 'Test this engine' }).click()

    const healthTable = modal.locator('.engine-health-table')
    await expect(healthTable).toBeVisible({ timeout: 10000 })
    await expect(healthTable.locator('.status-dot.status-done').first()).toBeVisible()

    await page.getByRole('button', { name: 'Close' }).click()
    await expect(modal).toHaveCount(0)
  })
})
