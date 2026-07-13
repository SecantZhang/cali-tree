import { expect, test } from '@playwright/test'
import { addNode, connectSockets, waitForPaletteLoaded } from '../helpers'

// addNode's id counter resets each fresh page load, so this click order fixes these ids.
const PEANUT_SOURCE = 'peanut_source-1'
const DATASET = 'dataset-2'
const JUDGE_ENGINE = 'lm_engine-3'
const HUMAN_ENGINE = 'lm_engine-4'
const CALIBRATION = 'cl_adversarial-5'
const PROMPT = 'judge_prompt-6'
const JUDGE = 'judge-7'

// The mock gateway always returns the same fixed score (3) for every call — the debate's
// judge-agent turn therefore always confirms it holds up (delta 0 < epsilon), so every
// item converges in round 1 with this exact addendum (see calibrated_result.py).
const OPTIMIZED_PROMPT_MARKER =
  'A prior adversarial review of this item confirmed the original score of 3 held up under scrutiny.'

test.describe('adversarial calibration node', () => {
  test('runs a debate over the dataset and the calibrated prompt reaches the downstream Judge node', async ({
    page,
  }) => {
    await page.goto('/')
    await waitForPaletteLoaded(page)
    await page.locator('.node-palette-item').filter({ hasText: /^cl_adversarial$/ }).waitFor({ state: 'visible' })

    await addNode(page, 'peanut_source')
    await addNode(page, 'dataset')
    await addNode(page, 'lm_engine')
    await addNode(page, 'lm_engine')
    await addNode(page, 'cl_adversarial')
    await addNode(page, 'judge_prompt')
    await addNode(page, 'judge')

    const peanutSourceNode = page.getByTestId(`rf__node-${PEANUT_SOURCE}`)
    const datasetNode = page.getByTestId(`rf__node-${DATASET}`)
    const calibrationNode = page.getByTestId(`rf__node-${CALIBRATION}`)
    const promptNode = page.getByTestId(`rf__node-${PROMPT}`)
    const judgeNode = page.getByTestId(`rf__node-${JUDGE}`)
    await expect(calibrationNode).toBeVisible()
    await expect(judgeNode).toBeVisible()

    await page.getByRole('button', { name: 'Fit View' }).click()

    // M3 is text-modality and the only metric with a human-annotation crosswalk in
    // ALIGNMENT (postprocessing/align.py) — matches mocked-live-pipeline.spec.ts's choice,
    // and lets this spec also assert a real human-score comparison in the secondary tab.
    await promptNode.locator('.param-row', { hasText: 'preset' }).locator('select').selectOption('M3')
    await calibrationNode.locator('.param-row', { hasText: 'metric_id' }).locator('select').selectOption('M3')
    // Disable retrieval so the debate never touches the real filesystem's human-annotation
    // corpus (this spec doesn't need retrieval grounding to prove the wiring works).
    await calibrationNode.locator('.param-row', { hasText: 'retrieval_enabled' })
      .locator('input[type="checkbox"]').uncheck()

    // Collapse the calibration node (six params) so its inline body doesn't visually
    // overlap the grid slot the palette placed later nodes in — same precaution
    // mocked-live-pipeline.spec.ts takes for the Judge node.
    await calibrationNode.getByRole('button', { name: 'Collapse node' }).click()

    await connectSockets(page, PEANUT_SOURCE, 'raw_dataset', DATASET, 'raw_dataset')
    await connectSockets(page, DATASET, 'samples', CALIBRATION, 'samples')
    await connectSockets(page, DATASET, 'labels', CALIBRATION, 'labels')
    await connectSockets(page, JUDGE_ENGINE, 'engine_config', CALIBRATION, 'judge_engine')
    await connectSockets(page, HUMAN_ENGINE, 'engine_config', CALIBRATION, 'human_engine')
    await connectSockets(page, DATASET, 'samples', JUDGE, 'samples')
    await connectSockets(page, JUDGE_ENGINE, 'engine_config', JUDGE, 'engine_config')
    await connectSockets(page, PROMPT, 'judge_spec', JUDGE, 'judge_spec')
    await connectSockets(page, CALIBRATION, 'calibration_results', JUDGE, 'calibration')

    await expect(page.getByTestId(`rf__edge-${DATASET}:samples->${CALIBRATION}:samples`)).toHaveCount(1)
    await expect(page.getByTestId(`rf__edge-${CALIBRATION}:calibration_results->${JUDGE}:calibration`)).toHaveCount(1)

    await page.locator('.dry-run-toggle input[type="checkbox"]').uncheck()
    page.once('dialog', (dialog) => dialog.accept())
    const runButton = page.getByRole('button', { name: /^Run(ning…)?$/ })
    await runButton.click()

    await expect(runButton).toHaveText('Run', { timeout: 30000 })
    for (const node of [peanutSourceNode, datasetNode, calibrationNode, judgeNode]) {
      await expect(node.locator('.status-dot.status-done')).toBeVisible()
    }

    // --- Calibration node's own secondary tab ---
    await calibrationNode.dblclick()
    const calibModal = page.locator('.modal-panel')
    await expect(calibModal).toBeVisible()
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
    await expect(scoreStrip).toContainText('converged')

    // The chat view rendered real alternating judge/human-proxy turns.
    const turns = calibModal.locator('.debate-turn')
    await expect(turns.first()).toBeVisible()
    await expect(calibModal.locator('.debate-turn-human-proxy').first()).toBeVisible()
    await expect(calibModal.locator('.debate-turn-judge').first()).toBeVisible()

    // Bottom-of-column reasoning + optimized prompt, for this selected item.
    await calibModal.locator('summary', { hasText: 'Calibrated reasoning' }).click()
    await expect(calibModal.locator('.reasoning')).toContainText('Original judge rationale')
    await calibModal.locator('summary', { hasText: 'Optimized prompt' }).click()
    await expect(calibModal.locator('.json-preview')).toContainText(OPTIMIZED_PROMPT_MARKER)

    await page.getByRole('button', { name: 'Close' }).click()
    await expect(calibModal).toHaveCount(0)

    // --- The concrete proof: the downstream Judge node's OWN secondary tab shows the
    // calibrated prompt actually reached its real LM call. ---
    await judgeNode.dblclick()
    const judgeModal = page.locator('.modal-panel')
    await expect(judgeModal).toBeVisible()
    const m3Card = judgeModal.locator('.rationale-card', { hasText: 'M3' }).first()
    await m3Card.locator('summary', { hasText: 'Prompt' }).click()
    await expect(m3Card.getByText(OPTIMIZED_PROMPT_MARKER, { exact: false })).toBeVisible()

    await page.getByRole('button', { name: 'Close' }).click()
    await expect(judgeModal).toHaveCount(0)
  })
})
