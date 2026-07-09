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
const WORKFLOW_NAME = 'stop_resume_e2e'

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

test.describe('stop and resume', () => {
  test('stopping a live run mid-flight leaves it resumable, and Resume finishes the rest from checkpoint', async ({
    page,
  }) => {
    await page.goto('/')
    await waitForPaletteLoaded(page)

    await addNode(page, 'peanut_source')
    await addNode(page, 'dataset')
    await addNode(page, 'lm_engine')
    await addNode(page, 'judge_text')
    await addNode(page, 'eval_text')

    const peanutSourceNode = page.getByTestId(`rf__node-${PEANUT_SOURCE}`)
    const datasetNode = page.getByTestId(`rf__node-${DATASET}`)
    const lmEngineNode = page.getByTestId(`rf__node-${LM_ENGINE}`)
    const judgeNode = page.getByTestId(`rf__node-${JUDGE}`)
    const evalNode = page.getByTestId(`rf__node-${EVAL}`)
    await page.getByRole('button', { name: 'Fit View' }).click()

    // Two text-modality metrics × 2 items = 4 real mock-gateway calls, run strictly
    // sequentially (text_concurrency defaults to 1) at the mock gateway's built-in ~200ms
    // per-call delay — long enough (~800ms total) to reliably click Stop mid-flight.
    const metricsRow = judgeNode.locator('.param-row', { hasText: 'metrics' })
    await metricsRow.locator('.checkbox-list-item', { hasText: 'M1' }).locator('input[type="checkbox"]').check()
    await metricsRow.locator('.checkbox-list-item', { hasText: 'M3' }).locator('input[type="checkbox"]').check()
    await judgeNode.getByRole('button', { name: 'Collapse node' }).click()

    await connect(page, PEANUT_SOURCE, 'raw_dataset', DATASET, 'raw_dataset')
    await connect(page, DATASET, 'samples', JUDGE, 'samples')
    await connect(page, LM_ENGINE, 'engine_config', JUDGE, 'engine_config')
    await connect(page, JUDGE, 'judge_result', EVAL, 'judge_result')
    await connect(page, DATASET, 'labels', EVAL, 'labels')
    await expect(page.getByTestId(`rf__edge-${PEANUT_SOURCE}:raw_dataset->${DATASET}:raw_dataset`)).toHaveCount(1)
    await expect(page.getByTestId(`rf__edge-${DATASET}:samples->${JUDGE}:samples`)).toHaveCount(1)
    await expect(page.getByTestId(`rf__edge-${LM_ENGINE}:engine_config->${JUDGE}:engine_config`)).toHaveCount(1)
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

    // Let roughly one and a half calls' worth of time pass, then stop mid-flight.
    await page.waitForTimeout(320)
    const stopButton = page.getByRole('button', { name: 'Stop' })
    await expect(stopButton).toBeVisible()
    await stopButton.click()

    await expect(page.getByRole('button', { name: /^Run(ning…)?$/ })).toHaveText('Run', { timeout: 20000 })
    await expect(page.locator('.console-header')).toContainText('Run status: stopped')

    // Judge itself finishes gracefully ("done" — it produced a real, if partial, result);
    // Eval never got to run at all ("stopped") since should_stop was already true by the
    // time the executor reached it (topological order: lm_engine, peanut_source, dataset,
    // judge_text, eval — Eval is always last).
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
    for (const node of [peanutSourceNode, datasetNode, lmEngineNode, judgeNode, evalNode]) {
      await expect(node.locator('.status-dot.status-done')).toBeVisible()
    }
    await expect(page.getByRole('button', { name: 'Resume' })).toHaveCount(0)

    // All 4 (item, metric) calls are accounted for by the end — some from the first
    // attempt, the rest completed after Resume.
    await judgeNode.dblclick()
    const judgeModal = page.locator('.modal-panel')
    await expect(judgeModal.locator('.secondary-summary')).toContainText('Valid calls: 4 / 4')
  })
})
