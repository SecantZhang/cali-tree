import { expect, type Locator, type Page, test } from '@playwright/test'
import { addNode, connectSockets, waitForPaletteLoaded } from '../helpers'

// The palette's auto-placement grid (NodesTab.tsx) wraps at 5 columns/280px, 220px row
// height. This graph has 8 nodes (more than any existing pipeline spec), spanning two
// grid rows whose combined height exceeds what fits in the canvas pane at React Flow's
// default minZoom (0.5) — Fit View can't zoom out past that floor, so the row-0 node in
// the last column ends up clipped by the pane's overflow. Playwright's `.toBeVisible()`
// doesn't account for clipping by an ancestor's `overflow: hidden`, so that clipped node
// still passes visibility checks while being un-draggable by a real mouse. Dragging it
// into the unused space just below an already-reachable node (rather than fighting
// zoom/fit) keeps the whole graph within the reachable area.
async function dragNodeIntoEmptySpace(page: Page, node: Locator) {
  const nodeBox = await node.boundingBox()
  const paneBox = await page.locator('.react-flow__pane').boundingBox()
  if (!nodeBox || !paneBox) throw new Error('dragNodeIntoEmptySpace: missing bounding box')
  // x+40/y+12: near the header's title text, left of the right-aligned Run/Collapse/Lock
  // buttons — dragging from those would trigger the button instead of a node move.
  const from = { x: nodeBox.x + 40, y: nodeBox.y + 12 }
  // A point near the pane's bottom-left: below every grid row this graph's 8 nodes can
  // occupy, and far from any other node's handles — genuinely empty space, rather than a
  // position computed relative to another node (which risks landing close enough to that
  // node's own handles to confuse the very next connect drag).
  const to = { x: paneBox.x + 60, y: paneBox.y + paneBox.height - 40 }
  await page.mouse.move(from.x, from.y)
  await page.mouse.down()
  await page.mouse.move((from.x + to.x) / 2, (from.y + to.y) / 2, { steps: 10 })
  await page.mouse.move(to.x, to.y, { steps: 10 })
  await page.waitForTimeout(50)
  await page.mouse.up()
}

async function dragNodeBy(page: Page, node: Locator, dx: number, dy: number) {
  const box = await node.boundingBox()
  if (!box) throw new Error('dragNodeBy: missing node bounding box')
  const from = { x: box.x + 40, y: box.y + 12 }
  await page.mouse.move(from.x, from.y)
  await page.mouse.down()
  await page.mouse.move(from.x + dx, from.y + dy, { steps: 12 })
  await page.mouse.up()
}

// This graph fans two source handles out to multiple targets (lm_engine-3 -> 3 different
// nodes, judge_prompt-5 -> 2) — every existing pipeline spec only ever connects a source
// once. Reusing the same output handle for a second/third drag in quick succession
// occasionally misses (React Flow resolves the drop handle from the DOM on the next
// frame — see dragConnect's own comment — and back-to-back drags from the same handle
// seem to be more prone to that race than a fresh handle each time). Verifying the edge
// actually landed and retrying once is more robust than guessing the exact internal
// timing cause.
async function connectSocketsVerified(
  page: Page,
  sourceNodeId: string, sourceHandleId: string,
  targetNodeId: string, targetHandleId: string,
): Promise<void> {
  const edge = page.getByTestId(
    `rf__edge-${sourceNodeId}:${sourceHandleId}->${targetNodeId}:${targetHandleId}`,
  )
  await connectSockets(page, sourceNodeId, sourceHandleId, targetNodeId, targetHandleId)
  try {
    // toHaveCount already polls — give the first attempt real time to land before
    // concluding it missed, rather than racing a retry drag against React's own render.
    await expect(edge).toHaveCount(1, { timeout: 3000 })
    return
  } catch {
    // Exactly one retry: if the first attempt truly never registered (not just slow to
    // render), a fresh drag is safe — the target socket has no existing edge to conflict
    // with (fan-in would otherwise reject a second one).
    await connectSockets(page, sourceNodeId, sourceHandleId, targetNodeId, targetHandleId)
    await expect(edge).toHaveCount(1)
  }
}

// addNode's id counter resets each fresh page load, so this click order fixes these ids.
// The graph is a real "sandwich": Judge (baseline) -judge_result-> Adversarial Calibration
// -calibration_results-> Judge (calibrated) — both Judge nodes share the same judge_spec +
// engine, so the only difference between them is the wired `calibration` input.
const PEANUT_SOURCE = 'peanut_source-1'
const DATASET = 'dataset-2'
const JUDGE_ENGINE = 'lm_engine-3'
const HUMAN_ENGINE = 'lm_engine-4'
const PROMPT = 'judge_prompt-5'
const JUDGE_BASELINE = 'judge-6'
const CALIBRATION = 'cl_adversarial-7'
const JUDGE_CALIBRATED = 'judge-8'

const OPTIMIZED_PROMPT_MARKER =
  'Evaluate audiovisual coherence across the complete edit.'

test.describe('adversarial calibration node', () => {
  test('calibrates an upstream Judge node\'s result and the optimized prompt reaches a second Judge node', async ({
    page,
  }) => {
    test.setTimeout(60000)
    await page.goto('/')
    await waitForPaletteLoaded(page)
    await page.locator('.node-palette-item').filter({ hasText: /^cl_adversarial$/ }).waitFor({ state: 'visible' })

    await addNode(page, 'peanut_source')
    await addNode(page, 'dataset')
    await addNode(page, 'lm_engine')
    await addNode(page, 'lm_engine')
    await addNode(page, 'judge_prompt')
    await addNode(page, 'judge')
    await addNode(page, 'cl_adversarial')
    await addNode(page, 'judge')

    const peanutSourceNode = page.getByTestId(`rf__node-${PEANUT_SOURCE}`)
    const datasetNode = page.getByTestId(`rf__node-${DATASET}`)
    const humanEngineNode = page.getByTestId(`rf__node-${HUMAN_ENGINE}`)
    const promptNode = page.getByTestId(`rf__node-${PROMPT}`)
    const judgeBaselineNode = page.getByTestId(`rf__node-${JUDGE_BASELINE}`)
    const calibrationNode = page.getByTestId(`rf__node-${CALIBRATION}`)
    const judgeCalibratedNode = page.getByTestId(`rf__node-${JUDGE_CALIBRATED}`)
    await expect(peanutSourceNode).toBeVisible()
    await expect(datasetNode).toBeVisible()
    await expect(humanEngineNode).toBeVisible()
    await expect(promptNode).toBeVisible()
    await expect(judgeBaselineNode).toBeVisible()
    await expect(calibrationNode).toBeVisible()
    await expect(judgeCalibratedNode).toBeVisible()

    // Fit View BEFORE anything else touches the canvas — the app persists zoom/pan
    // across loads, so the initial transform can be arbitrary (e.g. zoomed in) relative
    // to these freshly-added nodes' real positions.
    await page.getByRole('button', { name: 'Fit View' }).click()

    // Calibration needs one aggregated human anchor per item; the Dataset node now defaults to
    // "none" (per-rater), which calibration rejects — so pick mean here.
    await datasetNode.locator('.param-row', { hasText: 'aggregation_method' })
      .locator('select').selectOption('mean')

    // M3 is text-modality and the only metric with a human-annotation crosswalk in
    // ALIGNMENT (postprocessing/align.py) — matches mocked-live-pipeline.spec.ts's choice,
    // and lets this spec also assert a real human-score comparison in the secondary tab.
    await promptNode.locator('.param-row', { hasText: 'preset' }).locator('select').selectOption('M3')
    // Disable retrieval so the debate never touches the real filesystem's human-annotation
    // corpus (this spec doesn't need retrieval grounding to prove the wiring works).
    await calibrationNode.locator('.param-row', { hasText: 'retrieval_enabled' })
      .locator('input[type="checkbox"]').uncheck()

    // Configure before moving: the calibration node's eventual location overlaps the
    // minimap, which intentionally intercepts ordinary form clicks.
    await dragNodeIntoEmptySpace(page, promptNode)
    await dragNodeBy(page, promptNode, -30, 0)
    // Keep the calibration node's five densely-spaced input handles clear of the
    // baseline Judge. At some persisted viewport sizes their auto-grid boxes nearly
    // touch, causing real pointer drags to land on the Judge instead of human_engine.
    await dragNodeBy(page, calibrationNode, 170, 0)
    // The second engine initially occupies the last auto-grid column, where its right
    // output handle can sit underneath the fixed inspector panel. Move it fully inside
    // the canvas before reusing that handle for the human and summarizer connections.
    await dragNodeBy(page, humanEngineNode, -330, 190)

    await connectSocketsVerified(page, PEANUT_SOURCE, 'raw_dataset', DATASET, 'raw_dataset')

    await connectSocketsVerified(page, DATASET, 'samples', JUDGE_BASELINE, 'samples')
    await connectSocketsVerified(page, JUDGE_ENGINE, 'engine_config', JUDGE_BASELINE, 'engine_config')
    await connectSocketsVerified(page, PROMPT, 'judge_spec', JUDGE_BASELINE, 'judge_spec')

    await connectSocketsVerified(page, DATASET, 'samples', CALIBRATION, 'samples')
    await connectSocketsVerified(page, JUDGE_BASELINE, 'judge_result', CALIBRATION, 'judge_result')
    await connectSocketsVerified(page, DATASET, 'labels', CALIBRATION, 'labels')
    await connectSocketsVerified(page, JUDGE_ENGINE, 'engine_config', CALIBRATION, 'judge_engine')
    await connectSocketsVerified(page, HUMAN_ENGINE, 'engine_config', CALIBRATION, 'human_engine')
    await connectSocketsVerified(page, HUMAN_ENGINE, 'engine_config', CALIBRATION, 'summarizer_engine')

    await connectSocketsVerified(page, DATASET, 'samples', JUDGE_CALIBRATED, 'samples')
    await connectSocketsVerified(page, JUDGE_ENGINE, 'engine_config', JUDGE_CALIBRATED, 'engine_config')
    await connectSocketsVerified(page, PROMPT, 'judge_spec', JUDGE_CALIBRATED, 'judge_spec')
    await connectSocketsVerified(page, CALIBRATION, 'calibration_results', JUDGE_CALIBRATED, 'calibration')

    await expect(
      page.getByTestId(`rf__edge-${JUDGE_BASELINE}:judge_result->${CALIBRATION}:judge_result`),
    ).toHaveCount(1)
    await expect(
      page.getByTestId(`rf__edge-${CALIBRATION}:calibration_results->${JUDGE_CALIBRATED}:calibration`),
    ).toHaveCount(1)

    // Once every edge exists, use the product's own topological layout to remove the
    // temporary setup positions and keep every node/modal gesture unobstructed.
    await page.getByRole('button', { name: 'Auto layout' }).click()
    await page.waitForTimeout(450)

    await page.locator('.dry-run-toggle input[type="checkbox"]').uncheck()
    page.once('dialog', (dialog) => dialog.accept())
    const runButton = page.getByRole('button', { name: /^Run(ning…)?$/ })

    await runButton.click()
    await expect(calibrationNode.locator('.status-dot.status-running')).toBeVisible({ timeout: 15000 })

    // --- Calibration node's own secondary tab, opened while the debate is live ---
    await calibrationNode.dblclick()
    const calibModal = page.locator('.modal-panel')
    await expect(calibModal).toBeVisible()
    await expect(calibModal).toContainText('Live debate')
    // The original judge appears before either debate agent returns.
    await expect(calibModal.locator('.debate-turn-anchor').first()).toBeVisible()
    await expect(calibModal.locator('.debate-responding')).toBeVisible()
    // Each complete model turn is delivered immediately, before the node itself ends.
    await expect(calibModal.locator('.debate-turn-human-proxy').first()).toBeVisible()
    await expect(calibrationNode.locator('.status-dot.status-running')).toBeVisible()
    await expect(calibModal.locator('.debate-turn-judge').first()).toBeVisible()

    // The downstream calibrated judge is deliberately delayed by the local mock. The
    // calibration transcript must remain mounted throughout this intermediate state,
    // rather than disappearing until the overall run completes.
    await expect(calibrationNode.locator('.status-dot.status-done')).toBeVisible({ timeout: 15000 })
    await expect(judgeCalibratedNode.locator('.status-dot.status-running')).toBeVisible()
    await expect(calibModal.locator('.debate-turn-human-proxy').first()).toBeVisible()
    await expect(calibModal.locator('.debate-turn-judge').first()).toBeVisible()

    await expect(runButton).toHaveText('Run', { timeout: 30000 })
    for (const node of [peanutSourceNode, datasetNode, judgeBaselineNode, calibrationNode, judgeCalibratedNode]) {
      await expect(node.locator('.status-dot.status-done')).toBeVisible()
    }

    // The final REST-hydrated result replaces the live snapshot without a blank state.
    const calibSummary = calibModal.locator('.secondary-summary')
    await expect(calibSummary).toContainText('Items: 2')
    await expect(calibSummary).toContainText('Converged: 2 / 2')

    // Select the first item and inspect its per-item debate + score comparison.
    await calibModal.locator('.secondary-item-list li').first().click()
    const scoreStrip = calibModal.locator('.debate-score-strip')
    await expect(scoreStrip).toContainText('Original: 3')
    await expect(scoreStrip).toContainText('Calibrated: 3')
    // The fixture gives every sampled item a real human label for video_addresses_prompt
    // (the same dimension mocked-live-pipeline.spec.ts's Eval node computes MAE=1.000 with).
    await expect(scoreStrip).toContainText('Human (video_addresses_prompt): 4')
    // Rater count (n=) and the always-on raw gap (final_score=3 vs human=4) — both new,
    // computed regardless of Ground in human labels (left at its off default here).
    await expect(scoreStrip).toContainText(/n=\d+/)
    await expect(scoreStrip).toContainText('gap 1.00')
    await expect(scoreStrip).toContainText('converged')
    await expect(scoreStrip).toContainText('summary: llm')

    // The chat view opens with the upstream Judge node's own (baseline) run, followed
    // by real alternating judge/human-proxy debate turns. Left collapsed (not clicked
    // open) — the "Optimized prompt" assertion below relies on `.json-preview` being
    // unambiguous on the page, which opening this details block would break.
    const anchorBubble = calibModal.locator('.debate-turn-anchor')
    await expect(anchorBubble).toBeVisible()
    await expect(anchorBubble).toContainText('Original judge run')
    await expect(anchorBubble).toContainText('M3')
    await expect(anchorBubble.locator('summary', { hasText: 'Prompt' })).toBeVisible()

    const turns = calibModal.locator('.debate-turn')
    await expect(turns.first()).toBeVisible()
    await expect(calibModal.locator('.debate-turn-human-proxy').first()).toBeVisible()
    await expect(calibModal.locator('.debate-turn-judge').first()).toBeVisible()

    // Bottom-of-column reasoning + optimized prompt, for this selected item. Scoped to
    // the specific <details> block by summary text — the anchor bubble above also
    // renders `.json-preview` elements (its own system/user prompt, always in the DOM
    // regardless of <details> open state), so an unscoped `.json-preview` locator is
    // ambiguous now.
    await calibModal.locator('summary', { hasText: 'Calibrated reasoning' }).click()
    await expect(calibModal.locator('.reasoning')).toContainText('Original judge rationale')
    const optimizedPromptDetails = calibModal.locator('details').filter({ hasText: 'Optimized prompt' })
    await optimizedPromptDetails.locator('summary').click()
    await expect(optimizedPromptDetails.locator('.json-preview')).toContainText(OPTIMIZED_PROMPT_MARKER)

    await page.getByRole('button', { name: 'Close' }).click()
    await expect(calibModal).toHaveCount(0)

    // --- The baseline Judge node never saw any calibration input — its prompt must NOT
    // carry the optimized-prompt addendum. ---
    await judgeBaselineNode.dblclick()
    const baselineModal = page.locator('.modal-panel')
    await expect(baselineModal).toBeVisible()
    const baselineCard = baselineModal.locator('.rationale-card', { hasText: 'M3' }).first()
    await baselineCard.locator('summary', { hasText: 'Prompt' }).click()
    await expect(baselineCard.getByText(OPTIMIZED_PROMPT_MARKER, { exact: false })).toHaveCount(0)
    await page.getByRole('button', { name: 'Close' }).click()
    await expect(baselineModal).toHaveCount(0)

    // --- The concrete proof: the second Judge node's OWN secondary tab shows the
    // calibrated prompt actually reached its real LM call. ---
    await judgeCalibratedNode.dblclick()
    const calibratedJudgeModal = page.locator('.modal-panel')
    await expect(calibratedJudgeModal).toBeVisible()
    const calibratedCard = calibratedJudgeModal.locator('.rationale-card', { hasText: 'M3' }).first()
    await calibratedCard.locator('summary', { hasText: 'Prompt' }).click()
    await expect(calibratedCard.getByText(OPTIMIZED_PROMPT_MARKER, { exact: false })).toBeVisible()

    await page.getByRole('button', { name: 'Close' }).click()
    await expect(calibratedJudgeModal).toHaveCount(0)
  })
})
