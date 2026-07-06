import { expect, test } from '@playwright/test'
import { addNode, dragConnect, waitForPaletteLoaded } from '../helpers'

// addNode's module-level id counter (graphStore.ts) resets on every fresh page load, so
// clicking dataset, dataset, judge, eval in that order deterministically yields these ids.
// Same 4-node shape as dry-run-pipeline.spec.ts (a Dataset Node only ever populates one of
// its two output sockets per run — see dataset_node.py — so a `labels`-producing node needs
// its own human_annotations loader, separate from the `dataset`-producing peanut_eval one).
const PEANUT_DATASET = 'dataset-1'
const LABELS_DATASET = 'dataset-2'
const JUDGE = 'judge-3'
const EVAL = 'eval-4'

// The mock gateway (tests/e2e/mock_gateway.py) always returns score_1_to_5: 3 with these
// fixed reasoning lines, regardless of which metric/item was requested — see MOCK_JUDGE_CONTENT.
const MOCK_REASONING =
  'Mock gateway response for E2E testing. This is not a real judge call. Score is fixed at 3/5 for determinism.'

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

test.describe('mocked live pipeline', () => {
  test('runs the real Judge Node HTTP path against a mock gateway and shows real scores + a real MAE', async ({
    page,
  }) => {
    await page.goto('/')
    await waitForPaletteLoaded(page)

    await addNode(page, 'dataset')
    await addNode(page, 'dataset')
    await addNode(page, 'judge')
    await addNode(page, 'eval')

    const peanutDatasetNode = page.getByTestId(`rf__node-${PEANUT_DATASET}`)
    const labelsDatasetNode = page.getByTestId(`rf__node-${LABELS_DATASET}`)
    const judgeNode = page.getByTestId(`rf__node-${JUDGE}`)
    const evalNode = page.getByTestId(`rf__node-${EVAL}`)
    await expect(peanutDatasetNode).toBeVisible()
    await expect(labelsDatasetNode).toBeVisible()
    await expect(judgeNode).toBeVisible()
    await expect(evalNode).toBeVisible()

    await page.getByRole('button', { name: 'Fit View' }).click()

    await labelsDatasetNode
      .locator('.param-row', { hasText: 'loader' })
      .locator('select')
      .selectOption('human_annotations')

    // Restrict to M3 (text-modality; the only metric with a human-annotation crosswalk in
    // ALIGNMENT — see postprocessing/align.py) so this test makes exactly 2 mock HTTP calls
    // (one per fixture item) and never touches a video engine, which the mock gateway
    // doesn't emulate.
    await judgeNode
      .locator('.param-row', { hasText: 'metrics' })
      .locator('.checkbox-list-item', { hasText: 'M3' })
      .locator('input[type="checkbox"]')
      .check()

    // Judge's expanded param list is wide enough to visually overlap the grid slot the
    // palette placed Eval in (handles keep rendering regardless of collapse state, so
    // wiring below is unaffected) — collapse it so Eval is actually clickable afterward.
    await judgeNode.getByRole('button', { name: 'Collapse node' }).click()

    await connect(page, PEANUT_DATASET, 'dataset', JUDGE, 'dataset')
    await connect(page, JUDGE, 'judge_result', EVAL, 'judge_result')
    await connect(page, LABELS_DATASET, 'labels', EVAL, 'labels')
    await expect(page.getByTestId(`rf__edge-${PEANUT_DATASET}:dataset->${JUDGE}:dataset`)).toBeVisible()
    await expect(page.getByTestId(`rf__edge-${JUDGE}:judge_result->${EVAL}:judge_result`)).toBeVisible()
    await expect(page.getByTestId(`rf__edge-${LABELS_DATASET}:labels->${EVAL}:labels`)).toBeVisible()

    // Turn dry run off — this is the one spec that actually exercises the real Judge Node
    // HTTP path (against the mock gateway, never the real Pluto endpoint).
    await page.locator('.dry-run-toggle input[type="checkbox"]').uncheck()

    page.once('dialog', (dialog) => dialog.accept())
    const runButton = page.getByRole('button', { name: /^Run(ning…)?$/ })
    await runButton.click()

    await expect(runButton).toHaveText('Run', { timeout: 20000 })
    await expect(page.locator('.run-progress')).toHaveCount(0)

    for (const node of [peanutDatasetNode, labelsDatasetNode, judgeNode, evalNode]) {
      await expect(node.locator('.status-dot.status-done')).toBeVisible()
    }

    // Judge secondary tab: real scores parsed from the mock gateway's canned response.
    await judgeNode.dblclick()
    const judgeModal = page.locator('.modal-panel')
    await expect(judgeModal).toBeVisible()
    const judgeSummary = judgeModal.locator('.secondary-summary')
    await expect(judgeSummary).toContainText('Items: 2')
    await expect(judgeSummary).toContainText('Valid calls: 2 / 2')
    await expect(judgeSummary).toContainText('Avg score: 3.00 / 5')
    await expect(judgeModal.locator('.rationale-card', { hasText: 'M3' })).toContainText('score: 3')
    await expect(judgeModal.locator('.rationale-card', { hasText: 'M3' }).locator('.reasoning')).toHaveText(
      MOCK_REASONING,
    )
    await page.getByRole('button', { name: 'Close' }).click()
    await expect(judgeModal).toHaveCount(0)

    // Eval secondary tab: a real, non-null MAE computed from the mocked judge score (3)
    // against the fixture's human annotation for video_addresses_prompt (4).
    await evalNode.dblclick()
    const evalModal = page.locator('.modal-panel')
    await expect(evalModal).toBeVisible()
    await expect(evalModal.locator('p', { hasText: 'aligned item(s).' })).toHaveText('2 aligned item(s).')
    const row = evalModal.locator('.metrics-table tbody tr', { hasText: 'video_addresses_prompt' })
    await expect(row).toBeVisible()
    const cells = row.locator('td')
    await expect(cells.nth(1)).toHaveText('2') // n
    await expect(cells.nth(4)).toHaveText('1.000') // MAE = |4 - 3|
    await page.getByRole('button', { name: 'Close' }).click()
    await expect(evalModal).toHaveCount(0)
  })
})
