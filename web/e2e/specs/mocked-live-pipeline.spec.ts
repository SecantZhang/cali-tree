import { expect, test } from '@playwright/test'
import { addPipelineNodes, PIPELINE_IDS, waitForPaletteLoaded, wirePipeline } from '../helpers'

const { PEANUT_SOURCE, DATASET, LM_ENGINE, PROMPT, JUDGE, EVAL } = PIPELINE_IDS

// The mock gateway (tests/e2e/mock_gateway.py) always returns score_1_to_5: 3 with these
// fixed reasoning lines, regardless of which metric/item was requested — see MOCK_JUDGE_CONTENT.
const MOCK_REASONING =
  'Mock gateway response for E2E testing. This is not a real judge call. Score is fixed at 3/5 for determinism.'

for (const engineKind of ['gpt', 'gemini']) {
  test(`${engineKind}: runs the real Judge Node HTTP path against a mock gateway and shows real scores + a real MAE`, async ({
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
    await expect(peanutSourceNode).toBeVisible()
    await expect(judgeNode).toBeVisible()
    await expect(evalNode).toBeVisible()

    await page.getByRole('button', { name: 'Fit View' }).click()

    // The Dataset node now defaults to aggregation_method="none" (per-rater labels); this
    // test asserts judge-vs-consensus agreement, so pick mean (one aggregated score per item).
    await datasetNode.locator('.param-row', { hasText: 'aggregation_method' })
      .locator('select').selectOption('mean')

    // Use the M3 preset on the Judge Prompt node — M3 is text-modality and the only metric
    // with a human-annotation crosswalk in ALIGNMENT (see postprocessing/align.py), so this
    // makes exactly 2 mock HTTP calls (one per fixture item) and never touches a video
    // engine, which the mock gateway doesn't emulate.
    await promptNode.locator('.param-row', { hasText: 'preset' }).locator('select').selectOption('M3')

    // Judge's expanded param list can visually overlap the grid slot the palette placed Eval
    // in (handles keep rendering regardless of collapse state, so wiring below is
    // unaffected) — collapse it so Eval is actually clickable afterward.
    await judgeNode.getByRole('button', { name: 'Collapse node' }).click()

    await wirePipeline(page)
    await expect(page.getByTestId(`rf__edge-${LM_ENGINE}:engine_config->${JUDGE}:engine_config`)).toHaveCount(1)
    await lmEngineNode.locator('.param-row', { hasText: 'engine_kind' }).locator('select').selectOption(engineKind)
    await expect(page.getByTestId(`rf__edge-${DATASET}:samples->${JUDGE}:samples`)).toHaveCount(1)
    await expect(page.getByTestId(`rf__edge-${PROMPT}:judge_spec->${JUDGE}:judge_spec`)).toHaveCount(1)
    await expect(page.getByTestId(`rf__edge-${JUDGE}:judge_result->${EVAL}:judge_result`)).toHaveCount(1)
    await expect(page.getByTestId(`rf__edge-${DATASET}:labels->${EVAL}:labels`)).toHaveCount(1)

    // Turn dry run off — this is the one spec that actually exercises the real Judge Node
    // HTTP path (against the mock gateway, never the real Pluto endpoint).
    await page.locator('.dry-run-toggle input[type="checkbox"]').uncheck()

    page.once('dialog', (dialog) => dialog.accept())
    const runButton = page.getByRole('button', { name: /^Run(ning…)?$/ })
    await runButton.click()

    await expect(runButton).toHaveText('Run', { timeout: 20000 })
    // Top-bar progress bars stay mounted, returning to their idle state after the run.
    await expect(page.locator('.run-progress')).toBeVisible()

    for (const node of [peanutSourceNode, datasetNode, lmEngineNode, promptNode, judgeNode, evalNode]) {
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
    // Columns: Dimension(0) n(1) SRCC(2) PLCC(3) KRCC(4) MAE(5) QWK(6).
    const cells = row.locator('td')
    await expect(cells.nth(1)).toHaveText('2') // n
    await expect(cells.nth(5)).toHaveText('1.000') // MAE = |4 - 3|

    // Eval has no video path of its own (judge_result/labels never carry one) — it's
    // resolved client-side by tracing the wired graph back to the Dataset node feeding
    // Judge, then reading that node's own cached `dataset` output by item id.
    const evalVideo = evalModal.locator('video.item-video')
    await expect(evalVideo).toBeVisible()
    await expect(evalVideo).toHaveAttribute('src', /\/api\/media\?path=/)

    await page.getByRole('button', { name: 'Close' }).click()
    await expect(evalModal).toHaveCount(0)
  })
}
