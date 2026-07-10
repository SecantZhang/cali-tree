import { expect, test } from '@playwright/test'
import { addPipelineNodes, PIPELINE_IDS, waitForPaletteLoaded, wirePipeline } from '../helpers'

const { PEANUT_SOURCE, DATASET, LM_ENGINE, PROMPT, JUDGE, EVAL } = PIPELINE_IDS

test.describe('per-node Run / Re-run', () => {
  test('Run executes just the target node\'s ancestors, Re-run reuses them, and downstream nodes go stale', async ({
    page,
  }) => {
    await page.goto('/')
    await waitForPaletteLoaded(page)

    await addPipelineNodes(page)

    const peanutSourceNode = page.getByTestId(`rf__node-${PEANUT_SOURCE}`)
    const datasetNode = page.getByTestId(`rf__node-${DATASET}`)
    const lmEngineNode = page.getByTestId(`rf__node-${LM_ENGINE}`)
    const promptNode = page.getByTestId(`rf__node-${PROMPT}`)
    const judgeNode = page.getByTestId(`rf__node-${JUDGE}`)
    const evalNode = page.getByTestId(`rf__node-${EVAL}`)
    await page.getByRole('button', { name: 'Fit View' }).click()

    await judgeNode.getByRole('button', { name: 'Collapse node' }).click()

    await wirePipeline(page)

    // Re-run is disabled until a first run of some kind exists — nothing to reuse yet.
    await expect(judgeNode.getByRole('button', { name: 'Re-run node' })).toBeDisabled()

    // Baseline: a normal full-graph dry run establishes a `lastRunId` for Re-run to seed
    // from, and gives every node a real "done" status/result and an order badge to start
    // from (order/stale bookkeeping is asserted purely via the rendered DOM throughout this
    // test, not raw websocket frames — a fast/dry run commonly finishes before the socket
    // even connects, in which case the REST-response `order` fallback populates the same
    // state instead; either way, the DOM is the one place both paths agree).
    page.once('dialog', (dialog) => dialog.accept())
    await page.getByRole('button', { name: /^Run(ning…)?$/ }).click()
    await expect(page.getByRole('button', { name: /^Run(ning…)?$/ })).toHaveText('Run', { timeout: 20000 })
    for (const node of [peanutSourceNode, datasetNode, lmEngineNode, promptNode, judgeNode, evalNode]) {
      await expect(node.locator('.status-dot.status-done')).toBeVisible({ timeout: 10000 })
      await expect(node.locator('.rf-node-order-badge')).toBeVisible({ timeout: 10000 })
    }

    // run_id has only second-level resolution (matches CLAUDE.md's <YYMMDD-HH:MM:SS> log-dir
    // convention, same constraint stop-and-resume.spec.ts's Resume click works around) —
    // sleep past the second boundary so this scoped run gets a genuinely distinct id from
    // the baseline run above, same as a real user would by the time they click a button.
    await page.waitForTimeout(1100)

    // Click Judge's own Run (▶): executes Judge's ancestor closure (source/dataset/engine/
    // prompt) + Judge itself, fresh — Eval is downstream, not an ancestor, so it must NOT
    // run, and its now-outdated result is flagged stale immediately (before the run finishes).
    await judgeNode.getByRole('button', { name: 'Run node', exact: true }).click()
    await expect(evalNode.locator('.rf-node')).toHaveClass(/is-stale/)
    await expect(evalNode.locator('.rf-node-stale-badge')).toBeVisible()

    await expect(page.getByRole('button', { name: /^Run(ning…)?$/ })).toHaveText('Run', { timeout: 20000 })
    // This run's real scope was Judge's ancestor closure, not the full graph — every
    // ancestor (+ Judge itself) gets a fresh order badge, but Eval's disappears entirely
    // (it wasn't part of this run at all) while it stays visibly stale.
    for (const node of [peanutSourceNode, datasetNode, lmEngineNode, promptNode, judgeNode]) {
      await expect(node.locator('.rf-node-order-badge')).toBeVisible({ timeout: 10000 })
    }
    await expect(evalNode.locator('.rf-node-order-badge')).toHaveCount(0)
    await expect(evalNode.locator('.rf-node')).toHaveClass(/is-stale/)
    // Judge is the sink of its own ancestor closure (depends on both dataset and engine),
    // so it's always last in that closure's topological order, whatever the closure size.
    const closureSize = await page.locator('.rf-node-order-badge').count()
    await expect(judgeNode.locator('.rf-node-order-badge')).toHaveText(`[${closureSize}]`)

    await page.waitForTimeout(1100) // same run_id-collision guard as above

    // Click Judge's Re-run (↻): reuses the Run above's outputs for source/dataset/engine —
    // this run's real scope is just Judge itself, so only its own order badge survives.
    await expect(judgeNode.getByRole('button', { name: 'Re-run node' })).toBeEnabled()
    await judgeNode.getByRole('button', { name: 'Re-run node' }).click()

    await expect(page.getByRole('button', { name: /^Run(ning…)?$/ })).toHaveText('Run', { timeout: 20000 })
    await expect(judgeNode.locator('.rf-node-order-badge')).toHaveText('[1]', { timeout: 10000 })
    for (const node of [peanutSourceNode, datasetNode, lmEngineNode, promptNode]) {
      await expect(node.locator('.rf-node-order-badge')).toHaveCount(0)
    }
  })
})
