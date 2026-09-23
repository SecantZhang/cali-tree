import { expect, test } from '@playwright/test'
import { addNode, addPipelineNodes, PIPELINE_IDS, waitForPaletteLoaded, wirePipeline } from '../helpers'

// addNode's id counter lives inside each tab's own graphStore closure but still starts at 1
// per tab, so a fresh tab always yields these ids for its first nodes.
const { PEANUT_SOURCE, DATASET, JUDGE, EVAL } = PIPELINE_IDS

test.describe('tabbed workflows', () => {
  test('a live run in one tab keeps streaming in the background while a second tab is active', async ({
    page,
  }) => {
    await page.goto('/')
    await waitForPaletteLoaded(page)

    // Exactly one tab exists on a fresh load.
    await expect(page.locator('.tab-item')).toHaveCount(1)

    await addPipelineNodes(page)

    const peanutSourceNode = page.getByTestId(`rf__node-${PEANUT_SOURCE}`)
    const datasetNode = page.getByTestId(`rf__node-${DATASET}`)
    const judgeNode = page.getByTestId(`rf__node-${JUDGE}`)
    const evalNode = page.getByTestId(`rf__node-${EVAL}`)
    await page.getByRole('button', { name: 'Fit View' }).click()

    // Default M1 preset over 2 fixture items — the mock gateway's ~200ms per-call delay
    // gives enough of a window to switch tabs mid-run and observe it still in flight.
    await judgeNode.getByRole('button', { name: 'Collapse node' }).click()

    await wirePipeline(page)

    await page.locator('.dry-run-toggle input[type="checkbox"]').uncheck()
    page.once('dialog', (dialog) => dialog.accept())
    await page.getByRole('button', { name: /^Run(ning…)?$/ }).click()
    await expect(page.getByRole('button', { name: 'Running…' })).toBeVisible()

    // Open a second, blank tab while the first tab's run is still in flight.
    await page.getByRole('button', { name: 'New tab' }).click()
    await expect(page.locator('.tab-item')).toHaveCount(2)
    await expect(page.locator('.tab-item.active .tab-title')).toHaveText('Untitled')

    // The new tab has its own, independent (idle) run state and an empty canvas — it must
    // not show the first tab's in-flight run.
    await expect(page.locator('.console-header')).toContainText('Run status: idle')
    await expect(page.locator('.react-flow__node')).toHaveCount(0)

    // Switch back to the first tab: the run kept going the whole time in the background
    // (RunSocketManager mounts useRunSocket per-tab, unconditionally) and should complete
    // normally, not be stuck or reset.
    await page.locator('.tab-item').nth(0).click()
    await expect(page.getByRole('button', { name: /^Run(ning…)?$/ })).toHaveText('Run', { timeout: 20000 })
    await expect(page.locator('.console-header')).toContainText('Run status: done')
    for (const node of [peanutSourceNode, datasetNode, judgeNode, evalNode]) {
      await expect(node.locator('.status-dot.status-done')).toBeVisible()
    }
  })

  test('closing a dirty tab prompts to save; Discard closes without saving, Cancel keeps it open', async ({
    page,
  }) => {
    await page.goto('/')
    await waitForPaletteLoaded(page)

    await addNode(page, 'peanut_source')
    // Adding a node is a content-mutating graphStore action, so the tab is now dirty.
    await expect(page.locator('.tab-item .tab-title')).toContainText('•')

    await page.locator('.tab-item .tab-close').click()
    const modal = page.locator('.modal-panel', { hasText: 'unsaved changes' })
    await expect(modal).toBeVisible()

    // Cancel: modal closes, tab (and its unsaved node) is untouched.
    await modal.getByRole('button', { name: 'Cancel' }).click()
    await expect(modal).toHaveCount(0)
    await expect(page.locator('.tab-item')).toHaveCount(1)
    await expect(page.locator('.react-flow__node')).toHaveCount(1)

    // Discard: the tab (and its unsaved node) is gone — since it was the only tab, a fresh
    // blank one takes its place (App.tsx never leaves the app with zero tabs open).
    await page.locator('.tab-item .tab-close').click()
    await page.locator('.modal-panel', { hasText: 'unsaved changes' }).getByRole('button', { name: 'Discard' }).click()
    await expect(page.locator('.modal-panel', { hasText: 'unsaved changes' })).toHaveCount(0)
    await expect(page.locator('.tab-item')).toHaveCount(1)
    await expect(page.locator('.tab-item .tab-title')).not.toContainText('•')
    await expect(page.locator('.react-flow__node')).toHaveCount(0)
  })

  test('Cmd/Ctrl+S saves the active tab directly once it already names a saved workflow', async ({ page }) => {
    await page.goto('/')
    await waitForPaletteLoaded(page)

    await addNode(page, 'peanut_source')
    const workflowName = `e2e-tab-cmds-${Date.now()}`
    await page.getByRole('button', { name: 'Workflows', exact: true }).click()
    await page.getByPlaceholder('workflow name').fill(workflowName)
    await page.getByRole('button', { name: 'Save current graph' }).click()
    await expect(page.locator('.workflow-item', { hasText: workflowName })).toBeVisible()
    await expect(page.locator('.tab-item .tab-title')).not.toContainText('•')

    // Dirty it again, then save via the keyboard shortcut instead of the Workflows tab —
    // this must save directly (no name prompt) since the tab already names a workflow.
    await page.getByRole('button', { name: 'Nodes', exact: true }).click()
    await addNode(page, 'dataset')
    await expect(page.locator('.tab-item .tab-title')).toContainText('•')

    await page.keyboard.press('ControlOrMeta+s')
    await expect(page.locator('.tab-item .tab-title')).not.toContainText('•', { timeout: 5000 })

    // Confirm it actually persisted to the backend under the same name (2 nodes now).
    await page.reload()
    await waitForPaletteLoaded(page)
    await page.getByRole('button', { name: 'Workflows', exact: true }).click()
    await page
      .locator('.workflow-item', { hasText: workflowName })
      .getByRole('button', { name: 'Load' })
      .click()
    await expect(page.locator('.react-flow__node')).toHaveCount(2)
  })
})
