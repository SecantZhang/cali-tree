import { expect, test } from '@playwright/test'
import { addPipelineNodes, dragConnect, PIPELINE_IDS, waitForPaletteLoaded } from '../helpers'

const { PEANUT_SOURCE, DATASET, LM_ENGINE, PROMPT, JUDGE, EVAL } = PIPELINE_IDS

function paramRow(node: ReturnType<import('@playwright/test').Page['getByTestId']>, label: string) {
  return node.locator('.param-row', { hasText: label })
}

test.describe('graph building and workflow persistence', () => {
  test('builds a 6-node graph, connects sockets, edits inline params, collapses, and round-trips through a saved workflow', async ({
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
    await expect(datasetNode).toBeVisible()
    await expect(lmEngineNode).toBeVisible()
    await expect(promptNode).toBeVisible()
    await expect(judgeNode).toBeVisible()
    await expect(evalNode).toBeVisible()

    // Collapse Judge before fitting the view — Judge's expanded param list is tall enough
    // that fitting while it's still expanded can zoom out so far that adjacent nodes'
    // connecting edges render with a near-zero (Playwright-"hidden") bounding box, a real
    // rendering quirk found while writing this test, not a product bug. The palette also
    // places new nodes on a fixed grid that runs past the visible canvas width once there
    // are more than ~3 of them, so fitting is needed regardless for their handles to be
    // interactable (not clipped under the right panel).
    await judgeNode.getByRole('button', { name: 'Collapse node' }).click()
    await page.getByRole('button', { name: 'Fit View' }).click()

    // Connect peanut_source's "raw_dataset" source socket to dataset's "raw_dataset"
    // target socket, then dataset's "samples" to the judge's "samples".
    const sourceHandle = page.locator(`[data-nodeid="${PEANUT_SOURCE}"][data-handleid="raw_dataset"].source`)
    const targetHandle = page.locator(`[data-nodeid="${DATASET}"][data-handleid="raw_dataset"].target`)
    await dragConnect(page, sourceHandle, targetHandle)
    await expect(page.getByTestId(`rf__edge-${PEANUT_SOURCE}:raw_dataset->${DATASET}:raw_dataset`)).toHaveCount(1)

    const dsOutHandle = page.locator(`[data-nodeid="${DATASET}"][data-handleid="samples"].source`)
    const judgeInHandle = page.locator(`[data-nodeid="${JUDGE}"][data-handleid="samples"].target`)
    await dragConnect(page, dsOutHandle, judgeInHandle)
    await expect(page.getByTestId(`rf__edge-${DATASET}:samples->${JUDGE}:samples`)).toHaveCount(1)

    const engineOutHandle = page.locator(`[data-nodeid="${LM_ENGINE}"][data-handleid="engine_config"].source`)
    const judgeEngineInHandle = page.locator(`[data-nodeid="${JUDGE}"][data-handleid="engine_config"].target`)
    await dragConnect(page, engineOutHandle, judgeEngineInHandle)
    await expect(page.getByTestId(`rf__edge-${LM_ENGINE}:engine_config->${JUDGE}:engine_config`)).toHaveCount(1)

    // And the Judge Prompt node's `judge_spec` into the Judge — the metric is now a wired
    // artifact, not a param on the Judge node.
    const promptOutHandle = page.locator(`[data-nodeid="${PROMPT}"][data-handleid="judge_spec"].source`)
    const judgeSpecInHandle = page.locator(`[data-nodeid="${JUDGE}"][data-handleid="judge_spec"].target`)
    await dragConnect(page, promptOutHandle, judgeSpecInHandle)
    await expect(page.getByTestId(`rf__edge-${PROMPT}:judge_spec->${JUDGE}:judge_spec`)).toHaveCount(1)

    // Expand Judge again to edit its inline params below.
    await judgeNode.getByRole('button', { name: 'Expand node' }).click()

    // Edit an inline enum param directly on the dataset node body (no Inspector needed).
    const samplingModeRow = paramRow(datasetNode, 'sampling_mode')
    await samplingModeRow.locator('select').selectOption('stratified')
    await expect(samplingModeRow.locator('select')).toHaveValue('stratified')

    // Edit an inline list[string] param the same way.
    const useCaseFilterRow = paramRow(datasetNode, 'use_case_filter')
    await useCaseFilterRow.locator('input[type="text"]').fill('visual montage')
    await expect(useCaseFilterRow.locator('input[type="text"]')).toHaveValue('visual montage')

    // The Dataset node's inputs share one left edge (fixed-width label column), and the
    // single `require_labels` checkbox is pushed to the right edge instead of stretching.
    const inputLefts = await datasetNode
      .locator('.param-row > input:not([type="checkbox"]), .param-row > select')
      .evaluateAll((els) => els.map((el) => Math.round(el.getBoundingClientRect().left)))
    expect(inputLefts.length).toBeGreaterThan(1)
    expect(Math.max(...inputLefts) - Math.min(...inputLefts)).toBeLessThanOrEqual(1)
    const requireLabelsRow = paramRow(datasetNode, 'require_labels')
    const rowBox = await requireLabelsRow.boundingBox()
    const checkboxBox = await requireLabelsRow.locator('input[type="checkbox"]').boundingBox()
    // Checkbox sits at the row's right edge (its right edge is near the row's right edge,
    // well past the row's horizontal midpoint) — not floating centered in the row.
    expect(checkboxBox!.x).toBeGreaterThan(rowBox!.x + rowBox!.width / 2)

    // Edit an inline enum param (the metric preset) on the Judge Prompt node — change it
    // from the M1 default to M3.
    await paramRow(promptNode, 'preset').locator('select').selectOption('M3')

    // Collapse the Judge Prompt node and confirm the summary line reflects the preset.
    await promptNode.getByRole('button', { name: 'Collapse node' }).click()
    await expect(promptNode.locator('.rf-node-param')).toHaveText('metric: M3')
    await promptNode.getByRole('button', { name: 'Expand node' }).click()
    await expect(promptNode.locator('.rf-node-param')).toHaveCount(0)

    // Save the current graph as a named workflow.
    const workflowName = `e2e-test-workflow-${Date.now()}`
    await page.getByRole('button', { name: 'Workflows', exact: true }).click()
    await page.getByPlaceholder('workflow name').fill(workflowName)
    await page.getByRole('button', { name: 'Save current graph' }).click()
    await expect(page.locator('.workflow-item', { hasText: workflowName })).toBeVisible()

    // Reload the page: the canvas is in-memory only, so this proves nothing survives
    // except what actually round-trips through the backend's saved workflow.
    await page.reload()
    await waitForPaletteLoaded(page)
    await expect(page.locator('.react-flow__node')).toHaveCount(0)

    // Load the saved workflow back and confirm the graph — including the edited params —
    // reconstructs exactly, proving the toJSON -> POST -> GET -> loadGraph round trip.
    await page.getByRole('button', { name: 'Workflows', exact: true }).click()
    await page
      .locator('.workflow-item', { hasText: workflowName })
      .getByRole('button', { name: 'Load' })
      .click()

    await expect(page.locator('.react-flow__node')).toHaveCount(6)
    await expect(peanutSourceNode).toBeVisible()
    await expect(datasetNode).toBeVisible()
    await expect(lmEngineNode).toBeVisible()
    await expect(promptNode).toBeVisible()
    await expect(judgeNode).toBeVisible()
    await expect(evalNode).toBeVisible()
    await expect(page.getByTestId(`rf__edge-${PEANUT_SOURCE}:raw_dataset->${DATASET}:raw_dataset`)).toHaveCount(1)
    await expect(page.getByTestId(`rf__edge-${DATASET}:samples->${JUDGE}:samples`)).toHaveCount(1)
    await expect(page.getByTestId(`rf__edge-${LM_ENGINE}:engine_config->${JUDGE}:engine_config`)).toHaveCount(1)
    await expect(page.getByTestId(`rf__edge-${PROMPT}:judge_spec->${JUDGE}:judge_spec`)).toHaveCount(1)
    await expect(paramRow(datasetNode, 'sampling_mode').locator('select')).toHaveValue('stratified')
    await expect(paramRow(datasetNode, 'use_case_filter').locator('input[type="text"]')).toHaveValue('visual montage')
    // The edited metric preset round-tripped through save -> POST -> GET -> loadGraph.
    await expect(paramRow(promptNode, 'preset').locator('select')).toHaveValue('M3')
  })
})
