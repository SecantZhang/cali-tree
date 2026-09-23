import { expect, test } from '@playwright/test'
import { addPipelineNodes, PIPELINE_IDS, waitForPaletteLoaded, wirePipeline } from '../helpers'

const { DATASET, PROMPT, JUDGE, EVAL } = PIPELINE_IDS

test.describe('node locking', () => {
  test('locking a node locks its predecessors, makes them read-only, and a re-run skips them', async ({
    page,
  }) => {
    await page.goto('/')
    await waitForPaletteLoaded(page)

    await addPipelineNodes(page)
    const judgeNode = page.getByTestId(`rf__node-${JUDGE}`)
    const datasetNode = page.getByTestId(`rf__node-${DATASET}`)
    const evalNode = page.getByTestId(`rf__node-${EVAL}`)
    await page.getByRole('button', { name: 'Fit View' }).click()
    await judgeNode.getByRole('button', { name: 'Collapse node' }).click()
    await wirePipeline(page)

    // A dry run to completion — every node ends `done`, so it can be locked.
    const runButton = page.getByRole('button', { name: /^Run(ning…)?$/ })
    await runButton.click()
    await expect(runButton).toHaveText('Run', { timeout: 10000 })
    await expect(judgeNode.locator('.status-dot.status-done')).toBeVisible()

    // Lock the Judge via its own header lock button (🔒). It's enabled once the node + its
    // ancestors are done.
    const lockBtn = judgeNode.getByRole('button', { name: 'Lock node' })
    await expect(lockBtn).toBeEnabled()
    await lockBtn.click()

    // The Judge + its predecessors (Dataset, Prompt) lock; the downstream Eval does not.
    await expect(judgeNode.locator('.rf-node.is-locked')).toBeVisible()
    await expect(datasetNode.locator('.rf-node.is-locked')).toBeVisible()
    await expect(page.getByTestId(`rf__node-${PROMPT}`).locator('.rf-node.is-locked')).toBeVisible()
    await expect(evalNode.locator('.rf-node.is-locked')).toHaveCount(0)
    // The Judge's button now offers Unlock (🔓).
    await expect(judgeNode.getByRole('button', { name: 'Unlock node' })).toBeVisible()

    // run_id has only second-level resolution (matches CLAUDE.md's <YYMMDD-HH:MM:SS> log-dir
    // convention) — sleep past the second boundary so this locked re-run gets a distinct id
    // from the baseline run above (same guard scoped-run.spec.ts uses).
    await page.waitForTimeout(1100)

    // Re-run the whole graph: locked nodes are seeded/skipped (no fresh order badge), only
    // the unlocked Eval actually executes.
    await runButton.click()
    await expect(runButton).toHaveText('Run', { timeout: 10000 })
    await expect(evalNode.locator('.rf-node-order-badge')).toBeVisible({ timeout: 10000 })
    await expect(judgeNode.locator('.rf-node-order-badge')).toHaveCount(0)
    await expect(datasetNode.locator('.rf-node-order-badge')).toHaveCount(0)
    // Locked nodes stay done (result reused), not reset to idle.
    await expect(judgeNode.locator('.status-dot.status-done')).toBeVisible()
  })
})
