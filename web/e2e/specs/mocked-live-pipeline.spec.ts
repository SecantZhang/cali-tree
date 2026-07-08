import { expect, test } from '@playwright/test'
import { addNode, dragConnect, waitForPaletteLoaded } from '../helpers'

// addNode's module-level id counter (graphStore.ts) resets on every fresh page load, so
// clicking peanut_source, dataset, lm_engine, judge_text, eval in that order
// deterministically yields these ids.
const PEANUT_SOURCE = 'peanut_source-1'
const DATASET = 'dataset-2'
const LM_ENGINE = 'lm_engine-3'
const JUDGE = 'judge_text-4'
const EVAL = 'eval-5'

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

    await addNode(page, 'peanut_source')
    await addNode(page, 'dataset')
    await addNode(page, 'lm_engine')
    await addNode(page, 'judge_text')
    await addNode(page, 'eval')

    const peanutSourceNode = page.getByTestId(`rf__node-${PEANUT_SOURCE}`)
    const datasetNode = page.getByTestId(`rf__node-${DATASET}`)
    const lmEngineNode = page.getByTestId(`rf__node-${LM_ENGINE}`)
    const judgeNode = page.getByTestId(`rf__node-${JUDGE}`)
    const evalNode = page.getByTestId(`rf__node-${EVAL}`)
    await expect(peanutSourceNode).toBeVisible()
    await expect(datasetNode).toBeVisible()
    await expect(lmEngineNode).toBeVisible()
    await expect(judgeNode).toBeVisible()
    await expect(evalNode).toBeVisible()

    await page.getByRole('button', { name: 'Fit View' }).click()

    // Restrict to M3 (text-modality; the only metric with a human-annotation crosswalk in
    // ALIGNMENT — see postprocessing/align.py) so this test makes exactly 2 mock HTTP calls
    // (one per fixture item) and never touches a video engine, which the mock gateway
    // doesn't emulate. Both boxes start checked (an unset `metrics` runs every metric of
    // that modality, so the UI shows that honestly) — uncheck M1 to leave just M3.
    await judgeNode
      .locator('.param-row', { hasText: 'metrics' })
      .locator('.checkbox-list-item', { hasText: 'M1' })
      .locator('input[type="checkbox"]')
      .uncheck()

    // Judge's expanded param list is wide enough to visually overlap the grid slot the
    // palette placed Eval in (handles keep rendering regardless of collapse state, so
    // wiring below is unaffected) — collapse it so Eval is actually clickable afterward.
    await judgeNode.getByRole('button', { name: 'Collapse node' }).click()

    await connect(page, PEANUT_SOURCE, 'raw_dataset', DATASET, 'raw_dataset')
    await connect(page, DATASET, 'dataset', JUDGE, 'dataset')
    await connect(page, LM_ENGINE, 'engine_config', JUDGE, 'engine_config')
    await connect(page, JUDGE, 'judge_result', EVAL, 'judge_result_text')
    await connect(page, DATASET, 'labels', EVAL, 'labels')
    await expect(page.getByTestId(`rf__edge-${PEANUT_SOURCE}:raw_dataset->${DATASET}:raw_dataset`)).toHaveCount(1)
    await expect(page.getByTestId(`rf__edge-${DATASET}:dataset->${JUDGE}:dataset`)).toHaveCount(1)
    await expect(page.getByTestId(`rf__edge-${LM_ENGINE}:engine_config->${JUDGE}:engine_config`)).toHaveCount(1)
    await expect(page.getByTestId(`rf__edge-${JUDGE}:judge_result->${EVAL}:judge_result_text`)).toHaveCount(1)
    await expect(page.getByTestId(`rf__edge-${DATASET}:labels->${EVAL}:labels`)).toHaveCount(1)

    // Turn dry run off — this is the one spec that actually exercises the real Judge Node
    // HTTP path (against the mock gateway, never the real Pluto endpoint).
    await page.locator('.dry-run-toggle input[type="checkbox"]').uncheck()

    page.once('dialog', (dialog) => dialog.accept())
    const runButton = page.getByRole('button', { name: /^Run(ning…)?$/ })
    await runButton.click()

    await expect(runButton).toHaveText('Run', { timeout: 20000 })
    await expect(page.locator('.run-progress')).toHaveCount(0)

    for (const node of [peanutSourceNode, datasetNode, lmEngineNode, judgeNode, evalNode]) {
      await expect(node.locator('.status-dot.status-done')).toBeVisible()
    }

    // Peanut Source secondary tab: selecting an item renders a real <video> pointed at
    // the path-confined GET /api/media route (vejudge/interface/server/routes/media.py) —
    // the fixture's placeholder .mp4 won't actually decode in a real player, but this
    // proves the src URL is built and the item's real video path reaches it end to end.
    await peanutSourceNode.dblclick()
    const sourceModal = page.locator('.modal-panel')
    await expect(sourceModal).toBeVisible()
    await sourceModal.locator('.dataset-item-list li').first().click()
    const sourceVideo = sourceModal.locator('video.item-video')
    await expect(sourceVideo).toBeVisible()
    await expect(sourceVideo).toHaveAttribute('src', /\/api\/media\?path=/)
    await page.getByRole('button', { name: 'Close' }).click()
    await expect(sourceModal).toHaveCount(0)

    // Dataset secondary tab: both fixture items get a matching human label (the fixture
    // gives every project exactly one annotated prompt at index 0) — proves the `labels`
    // output is a real item-id join against this node's own sampled set, not an empty stub.
    await datasetNode.dblclick()
    const datasetModal = page.locator('.modal-panel')
    await expect(datasetModal).toBeVisible()
    await expect(datasetModal.locator('.secondary-summary')).toContainText(
      '2 / 2 item(s) selected, 2 with matching human label(s)',
    )
    await page.getByRole('button', { name: 'Close' }).click()
    await expect(datasetModal).toHaveCount(0)

    // Judge secondary tab: real scores parsed from the mock gateway's canned response.
    await judgeNode.dblclick()
    const judgeModal = page.locator('.modal-panel')
    await expect(judgeModal).toBeVisible()
    const judgeSummary = judgeModal.locator('.secondary-summary')
    await expect(judgeSummary).toContainText('Items: 2')
    await expect(judgeSummary).toContainText('Valid calls: 2 / 2')
    await expect(judgeSummary).toContainText('Avg score: 3.00 / 5')

    // The live score-distribution histogram (recharts) actually rendered against these
    // real results, not just the summary strip's numbers.
    await expect(judgeModal.locator('.secondary-chart svg')).toBeVisible()

    await expect(judgeModal.locator('.rationale-card', { hasText: 'M3' })).toContainText('score: 3')
    await expect(judgeModal.locator('.rationale-card', { hasText: 'M3' }).locator('.reasoning')).toHaveText(
      MOCK_REASONING,
    )

    // The actual prompt text sent to the LM, not just the parsed output — the fixture's
    // real user_request ("make a video") must appear in the User prompt once expanded.
    const m3Card = judgeModal.locator('.rationale-card', { hasText: 'M3' })
    await m3Card.locator('summary', { hasText: 'Prompt' }).click()
    await expect(m3Card.getByText('make a video')).toBeVisible()

    await page.getByRole('button', { name: 'Close' }).click()
    await expect(judgeModal).toHaveCount(0)

    // Eval secondary tab: a real, non-null MAE computed from the mocked judge score (3)
    // against the fixture's human annotation for video_addresses_prompt (4).
    await evalNode.dblclick()
    const evalModal = page.locator('.modal-panel')
    await expect(evalModal).toBeVisible()
    await expect(evalModal.locator('p', { hasText: 'aligned item(s).' })).toHaveText('2 aligned item(s).')

    // The live human-vs-judge scatter plot (recharts) rendered against these real
    // aligned rows, not just the summary table below it. Scoped to the main chart's own
    // svg (role="application") — the per-dimension legend icons are also <svg> elements.
    await expect(evalModal.locator('.secondary-chart svg[role="application"]')).toBeVisible()

    const row = evalModal.locator('.metrics-table tbody tr', { hasText: 'video_addresses_prompt' })
    await expect(row).toBeVisible()
    const cells = row.locator('td')
    await expect(cells.nth(1)).toHaveText('2') // n
    await expect(cells.nth(4)).toHaveText('1.000') // MAE = |4 - 3|

    // Eval has no video path of its own (judge_result/labels never carry one) — it's
    // resolved client-side by tracing the wired graph back to the Dataset node feeding
    // Judge, then reading that node's own cached `dataset` output by item id.
    const evalVideo = evalModal.locator('video.item-video')
    await expect(evalVideo).toBeVisible()
    await expect(evalVideo).toHaveAttribute('src', /\/api\/media\?path=/)

    await page.getByRole('button', { name: 'Close' }).click()
    await expect(evalModal).toHaveCount(0)
  })
})
