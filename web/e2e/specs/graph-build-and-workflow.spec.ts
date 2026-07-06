import { expect, test } from '@playwright/test'
import { addNode, dragConnect, waitForPaletteLoaded } from '../helpers'

// addNode's module-level id counter (graphStore.ts) resets on every fresh page load, so
// clicking dataset, dataset, judge, eval in that order deterministically yields these ids.
const DATASET_1 = 'dataset-1'
const DATASET_2 = 'dataset-2'
const JUDGE = 'judge-3'
const EVAL = 'eval-4'

function paramRow(node: ReturnType<import('@playwright/test').Page['getByTestId']>, label: string) {
  return node.locator('.param-row', { hasText: label })
}

test.describe('graph building and workflow persistence', () => {
  test('builds a 4-node graph, connects sockets, edits inline params, collapses, and round-trips through a saved workflow', async ({
    page,
  }) => {
    await page.goto('/')
    await waitForPaletteLoaded(page)

    await addNode(page, 'dataset')
    await addNode(page, 'dataset')
    await addNode(page, 'judge')
    await addNode(page, 'eval')

    const datasetNode1 = page.getByTestId(`rf__node-${DATASET_1}`)
    const datasetNode2 = page.getByTestId(`rf__node-${DATASET_2}`)
    const judgeNode = page.getByTestId(`rf__node-${JUDGE}`)
    const evalNode = page.getByTestId(`rf__node-${EVAL}`)
    await expect(datasetNode1).toBeVisible()
    await expect(datasetNode2).toBeVisible()
    await expect(judgeNode).toBeVisible()
    await expect(evalNode).toBeVisible()

    // The palette places new nodes on a fixed grid that runs past the visible canvas
    // width once there are more than ~3 of them — fit them all into view first so their
    // handles are actually interactable (not clipped under the right panel).
    await page.getByRole('button', { name: 'Fit View' }).click()

    // Connect dataset-1's "dataset" source socket to judge-3's "dataset" target socket.
    const sourceHandle = page.locator(`[data-nodeid="${DATASET_1}"][data-handleid="dataset"].source`)
    const targetHandle = page.locator(`[data-nodeid="${JUDGE}"][data-handleid="dataset"].target`)
    await dragConnect(page, sourceHandle, targetHandle)
    await expect(page.getByTestId(`rf__edge-${DATASET_1}:dataset->${JUDGE}:dataset`)).toBeVisible()

    // Edit an inline enum param directly on the dataset-1 node body (no Inspector needed).
    const loaderRow = paramRow(datasetNode1, 'loader')
    await loaderRow.locator('select').selectOption('human_annotations')
    await expect(loaderRow.locator('select')).toHaveValue('human_annotations')

    // Edit an inline list[string] param the same way.
    const projectsRow = paramRow(datasetNode1, 'projects')
    await projectsRow.locator('input[type="text"]').fill('prj-a')
    await expect(projectsRow.locator('input[type="text"]')).toHaveValue('prj-a')

    // Edit an inline list[enum] param (checkbox list) on the judge node.
    const metricsRow = paramRow(judgeNode, 'metrics')
    await metricsRow.locator('.checkbox-list-item', { hasText: 'M1' }).locator('input[type="checkbox"]').check()

    // Collapse the judge node and confirm the summary line reflects the selected metric.
    await judgeNode.getByRole('button', { name: 'Collapse node' }).click()
    await expect(judgeNode.locator('.rf-node-param')).toHaveText('metrics: M1')
    await judgeNode.getByRole('button', { name: 'Expand node' }).click()
    await expect(judgeNode.locator('.rf-node-param')).toHaveCount(0)

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

    await expect(page.locator('.react-flow__node')).toHaveCount(4)
    await expect(datasetNode1).toBeVisible()
    await expect(datasetNode2).toBeVisible()
    await expect(judgeNode).toBeVisible()
    await expect(evalNode).toBeVisible()
    await expect(page.getByTestId(`rf__edge-${DATASET_1}:dataset->${JUDGE}:dataset`)).toBeVisible()
    await expect(paramRow(datasetNode1, 'loader').locator('select')).toHaveValue('human_annotations')
    await expect(paramRow(datasetNode1, 'projects').locator('input[type="text"]')).toHaveValue('prj-a')
    await expect(
      paramRow(judgeNode, 'metrics').locator('.checkbox-list-item', { hasText: 'M1' }).locator('input[type="checkbox"]'),
    ).toBeChecked()
  })
})
