import { expect, test } from '@playwright/test'
import { addPipelineNodes, PIPELINE_IDS, waitForPaletteLoaded, wirePipeline } from '../helpers'

const { PEANUT_SOURCE, DATASET, LM_ENGINE, PROMPT, JUDGE, EVAL } = PIPELINE_IDS
const WORKFLOW_NAME = 'stop_resume_e2e'

test.describe('stop and resume', () => {
  test('stopping a live run mid-flight leaves it resumable, and Resume finishes the rest from checkpoint', async ({
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

    // Default M1 preset (text modality) × 2 fixture items = 2 real mock-gateway calls, run
    // strictly sequentially (concurrency defaults to 1) at the mock's ~200ms per-call delay.
    await judgeNode.getByRole('button', { name: 'Collapse node' }).click()

    await wirePipeline(page)
    await expect(page.getByTestId(`rf__edge-${DATASET}:samples->${JUDGE}:samples`)).toHaveCount(1)
    await expect(page.getByTestId(`rf__edge-${PROMPT}:judge_spec->${JUDGE}:judge_spec`)).toHaveCount(1)
    await expect(page.getByTestId(`rf__edge-${JUDGE}:judge_result->${EVAL}:judge_result`)).toHaveCount(1)
    await expect(page.getByTestId(`rf__edge-${DATASET}:labels->${EVAL}:labels`)).toHaveCount(1)

    // Save as a named workflow first — Resume is only auto-offered for a saved workflow's
    // own prior runs (see RunControls.tsx), matched by workflow_name tagged onto the run.
    await page.getByRole('button', { name: 'Workflows', exact: true }).click()
    await page.getByPlaceholder('workflow name').fill(WORKFLOW_NAME)
    await page.getByRole('button', { name: 'Save current graph' }).click()
    await expect(page.locator('.workflow-item', { hasText: WORKFLOW_NAME })).toBeVisible()

    await page.locator('.dry-run-toggle input[type="checkbox"]').uncheck()
    page.once('dialog', (dialog) => dialog.accept())
    await page.getByRole('button', { name: /^Run(ning…)?$/ }).click()

    // Stop partway through the first call — the second item is still queued (concurrency 1),
    // so it gets cancelled and only completes on Resume from checkpoint.
    await page.waitForTimeout(120)
    const stopButton = page.getByRole('button', { name: 'Stop' })
    await expect(stopButton).toBeVisible()
    await stopButton.click()

    await expect(page.getByRole('button', { name: /^Run(ning…)?$/ })).toHaveText('Run', { timeout: 20000 })
    await expect(page.locator('.console-header')).toContainText('Run status: stopped')

    // Judge itself finishes gracefully ("done" — it produced a real, if partial, result);
    // Eval never got to run at all ("stopped") since should_stop was already true by the
    // time the executor reached it (topological order: lm_engine, peanut_source, dataset,
    // judge, eval — Eval is always last).
    await expect(judgeNode.locator('.status-dot.status-done')).toBeVisible()
    await expect(evalNode.locator('.status-dot.status-stopped')).toBeVisible()

    // Resume: reopens the same run directory/checkpoint, so already-completed (item,
    // metric) pairs are reused and only the missing ones make fresh calls.
    const resumeButton = page.getByRole('button', { name: 'Resume' })
    await expect(resumeButton).toBeVisible()
    page.once('dialog', (dialog) => dialog.accept())
    await resumeButton.click()

    await expect(page.getByRole('button', { name: /^Run(ning…)?$/ })).toHaveText('Run', { timeout: 20000 })
    await expect(page.locator('.console-header')).toContainText('Run status: done')
    for (const node of [peanutSourceNode, datasetNode, lmEngineNode, promptNode, judgeNode, evalNode]) {
      await expect(node.locator('.status-dot.status-done')).toBeVisible()
    }
    await expect(page.getByRole('button', { name: 'Resume' })).toHaveCount(0)

    // Both item calls are accounted for by the end — one from the first attempt (checkpointed
    // before Stop), the other completed after Resume.
    await judgeNode.dblclick()
    const judgeModal = page.locator('.modal-panel')
    await expect(judgeModal.locator('.secondary-summary')).toContainText('Valid calls: 2 / 2')
  })
})
