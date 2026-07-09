import { expect, test } from '@playwright/test'
import { addNode, dragConnect, waitForPaletteLoaded } from '../helpers'

// addNode's module-level id counter (graphStore.ts) resets on every fresh page load, so
// clicking peanut_source, dataset, lm_engine, judge_text, eval_text in that order
// deterministically yields these ids.
const PEANUT_SOURCE = 'peanut_source-1'
const DATASET = 'dataset-2'
const LM_ENGINE = 'lm_engine-3'
const JUDGE = 'judge_text-4'
const EVAL = 'eval_text-5'

async function connect(
  page: import('@playwright/test').Page,
  sourceNodeId: string,
  sourceHandleId: string,
  targetNodeId: string,
  targetHandleId: string,
) {
  const source = page.locator(`[data-nodeid="${sourceNodeId}"][data-handleid="${sourceHandleId}"].source`)
  const target = page.locator(`[data-nodeid="${targetNodeId}"][data-handleid="${targetHandleId}"].target`)
  await dragConnect(page, source, target)
}

test.describe('eval node diagnostics', () => {
  test('a live run with real item-id overlap but a metric that never ran explains why, instead of an opaque empty table', async ({
    page,
  }) => {
    await page.goto('/')
    await waitForPaletteLoaded(page)

    await addNode(page, 'peanut_source')
    await addNode(page, 'dataset')
    await addNode(page, 'lm_engine')
    await addNode(page, 'judge_text')
    await addNode(page, 'eval_text')

    const datasetNode = page.getByTestId(`rf__node-${DATASET}`)
    const judgeNode = page.getByTestId(`rf__node-${JUDGE}`)
    const evalNode = page.getByTestId(`rf__node-${EVAL}`)
    await page.getByRole('button', { name: 'Fit View' }).click()

    // M1 only, never M3 — M3 is the only text metric with a human-annotation crosswalk
    // (postprocessing/align.py's ALIGNMENT), so real item-id overlap exists (M1 still ran
    // and produced judge_result rows) but every aligned dimension ends up with n == 0.
    await judgeNode
      .locator('.param-row', { hasText: 'metrics' })
      .locator('.checkbox-list-item', { hasText: 'M3' })
      .locator('input[type="checkbox"]')
      .uncheck()
    await judgeNode.getByRole('button', { name: 'Collapse node' }).click()

    await connect(page, PEANUT_SOURCE, 'raw_dataset', DATASET, 'raw_dataset')
    await connect(page, DATASET, 'dataset', JUDGE, 'dataset')
    await connect(page, LM_ENGINE, 'engine_config', JUDGE, 'engine_config')
    await connect(page, JUDGE, 'judge_result', EVAL, 'judge_result')
    await connect(page, DATASET, 'labels', EVAL, 'labels')

    await page.locator('.dry-run-toggle input[type="checkbox"]').uncheck()
    page.once('dialog', (dialog) => dialog.accept())
    await page.getByRole('button', { name: /^Run(ning…)?$/ }).click()
    await expect(page.getByRole('button', { name: /^Run(ning…)?$/ })).toHaveText('Run', { timeout: 20000 })

    await evalNode.dblclick()
    const evalModal = page.locator('.modal-panel')
    await expect(evalModal).toBeVisible()
    // Real overlap (Judge ran, produced M1 rows for both items) — never the "0 aligned
    // items" warning, which only fires when item ids themselves never overlapped at all.
    await expect(evalModal.locator('p', { hasText: 'aligned item(s).' })).toHaveText('2 aligned item(s).')
    await expect(evalModal.getByText('No dimensions had matched human + judge scores.')).toBeVisible()
    const diagnostics = evalModal.locator('.eval-diagnostics')
    await expect(diagnostics).toBeVisible()
    await expect(diagnostics).toContainText('video_addresses_prompt')
    await expect(diagnostics).toContainText('never produced')
    await page.getByRole('button', { name: 'Close' }).click()
    await expect(evalModal).toHaveCount(0)
  })
})
