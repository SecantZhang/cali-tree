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

    // Temperature 9.9 is the mock gateway's deliberate 3-second delay sentinel. A hard
    // Stop must return while that first real HTTP request is still blocked, not after it.
    await lmEngineNode.locator('.param-row', { hasText: 'temperature' }).locator('input').fill('9.9')
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

    // Stop partway through the first call. Neither the active item nor the queued second
    // item is checkpointed, and the isolated worker must die immediately.
    await page.waitForTimeout(500)
    const stopButton = page.getByRole('button', { name: 'Stop' })
    await expect(stopButton).toBeVisible()
    const stopStarted = Date.now()
    await stopButton.click()

    await expect(page.getByRole('button', { name: /^Run(ning…)?$/ })).toHaveText('Run', { timeout: 1500 })
    expect(Date.now() - stopStarted).toBeLessThan(1500)
    await expect(page.locator('.console-header')).toContainText('Run status: stopped')

    // The active Judge and pending Eval are both terminal immediately. Fast upstream nodes
    // completed before the kill and retain their ordinary done results.
    await expect(judgeNode.locator('.status-dot.status-stopped')).toBeVisible()
    await expect(evalNode.locator('.status-dot.status-stopped')).toBeVisible()

    // Resume: reopens the same run directory/checkpoint, so already-completed (item,
    // metric) pairs are reused and only the missing ones make fresh calls.
    const resumeButton = page.getByRole('button', { name: 'Resume' })
    await expect(resumeButton).toBeVisible()
    page.once('dialog', (dialog) => dialog.accept())
    await resumeButton.click()

    // First observe the resumed attempt actually start; otherwise an immediate `Run`
    // assertion can pass against the stopped attempt before resumeRun's POST resolves.
    await expect(page.getByRole('button', { name: /^Run(ning…)?$/ })).toHaveText('Running…')
    await expect(page.getByRole('button', { name: /^Run(ning…)?$/ })).toHaveText('Run', { timeout: 30000 })
    await expect(page.locator('.console-header')).toContainText('Run status: done')
    for (const node of [peanutSourceNode, datasetNode, lmEngineNode, promptNode, judgeNode, evalNode]) {
      await expect(node.locator('.status-dot.status-done')).toBeVisible()
    }
    await expect(page.getByRole('button', { name: 'Resume' })).toHaveCount(0)

    // Both item calls are accounted for after Resume. The killed in-flight call was not
    // checkpointed, so it was safely rerun along with the item that had remained queued.
    await judgeNode.dblclick()
    const judgeModal = page.locator('.modal-panel')
    await expect(judgeModal.locator('.secondary-summary')).toContainText('Valid calls: 2 / 2')
  })
})
