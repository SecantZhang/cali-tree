import { expect, test } from '@playwright/test'
import { addPipelineNodes, PIPELINE_IDS, waitForPaletteLoaded, wirePipeline } from '../helpers'

// The per-metric pipeline: Peanut Source -> Dataset -> Judge (with LM Engine + a Judge
// Prompt preset) -> Eval, plus Dataset.labels -> Eval. `engine_config` and `judge_spec` are
// required Judge inputs even in dry-run mode (the check happens before the dry-run branch),
// so both an LM Engine and a Judge Prompt node must be wired regardless of a gateway call.
const { PEANUT_SOURCE, DATASET, LM_ENGINE, PROMPT, JUDGE, EVAL } = PIPELINE_IDS

test.describe('dry-run pipeline', () => {
  test('runs a fully wired per-metric graph in dry-run mode end to end', async ({ page }) => {
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
    await expect(datasetNode).toBeVisible()
    await expect(lmEngineNode).toBeVisible()
    await expect(promptNode).toBeVisible()
    await expect(judgeNode).toBeVisible()
    await expect(evalNode).toBeVisible()

    // The model dropdown is scoped to the sibling engine_kind param (modelCatalog.ts) —
    // switching families must repopulate the model options and land on a valid default
    // for the new family, not leave a stale model string from the old one selected.
    const modelSelect = lmEngineNode.locator('.param-row', { hasText: 'model' }).locator('select')
    await expect(modelSelect).toHaveValue('gpt-4.1')
    await lmEngineNode.locator('.param-row', { hasText: 'engine_kind' }).locator('select').selectOption('claude')
    await expect(modelSelect).toHaveValue('claude-haiku-4.5')
    await expect(modelSelect.locator('option')).toHaveCount(7)

    // Fit View before collapsing (not after) — matching the other specs in this suite;
    // computing the fit against Judge's still-expanded height first, then collapsing,
    // avoids a zoom level that leaves adjacent nodes' connecting edges too close together
    // to render with a real (non-degenerate) bounding box.
    await page.getByRole('button', { name: 'Fit View' }).click()
    await judgeNode.getByRole('button', { name: 'Collapse node' }).click()

    // Wire the full per-metric pipeline (see wirePipeline): source -> dataset -> judge ->
    // eval, plus the LM Engine + Judge Prompt inputs to judge and Dataset.labels to eval.
    await wirePipeline(page)
    await expect(page.getByTestId(`rf__edge-${PEANUT_SOURCE}:raw_dataset->${DATASET}:raw_dataset`)).toHaveCount(1)
    await expect(page.getByTestId(`rf__edge-${DATASET}:samples->${JUDGE}:samples`)).toHaveCount(1)
    await expect(page.getByTestId(`rf__edge-${LM_ENGINE}:engine_config->${JUDGE}:engine_config`)).toHaveCount(1)
    await expect(page.getByTestId(`rf__edge-${PROMPT}:judge_spec->${JUDGE}:judge_spec`)).toHaveCount(1)
    await expect(page.getByTestId(`rf__edge-${JUDGE}:judge_result->${EVAL}:judge_result`)).toHaveCount(1)
    await expect(page.getByTestId(`rf__edge-${DATASET}:labels->${EVAL}:labels`)).toHaveCount(1)

    // Dry run is on by default — no confirm dialog, no gateway calls.
    await expect(page.locator('.dry-run-toggle input[type="checkbox"]')).toBeChecked()

    // The top-bar progress bars are always mounted now (they show a flat "Idle" state
    // before/after a run instead of disappearing), so the run-progress container is present
    // regardless of run state.
    const runProgress = page.locator('.run-progress')
    await expect(runProgress).toBeVisible()
    await expect(runProgress.getByText('Idle — no run in progress')).toBeVisible()

    const runButton = page.getByRole('button', { name: /^Run(ning…)?$/ })
    await runButton.click()

    await expect(runButton).toHaveText('Run', { timeout: 10000 })
    // Back to the idle state once the run completes — still present, not removed.
    await expect(runProgress).toBeVisible()
    await expect(runProgress.getByText('Idle — no run in progress')).toBeVisible()

    for (const node of [peanutSourceNode, datasetNode, lmEngineNode, promptNode, judgeNode, evalNode]) {
      await expect(node.locator('.status-dot.status-done')).toBeVisible()
    }

    // Open the Eval node's secondary tab and confirm it renders a real (if necessarily
    // empty) report: dry-run Judge Node produces no judge_result rows, so Eval has nothing
    // to align against the human labels — but the report itself must still be well-formed.
    await evalNode.dblclick()
    const modal = page.locator('.modal-panel')
    await expect(modal).toBeVisible()
    await expect(modal.getByText('0 aligned item(s).')).toBeVisible()
    await expect(modal.getByText('No dimensions had matched human + judge scores.')).toBeVisible()
    await page.getByRole('button', { name: 'Close' }).click()
    await expect(modal).toHaveCount(0)
  })
})
