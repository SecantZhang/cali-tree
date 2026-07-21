import { expect, test } from '@playwright/test'
import {
  addNode,
  addPipelineNodes,
  connectSockets,
  dragConnect,
  PIPELINE_IDS,
  waitForPaletteLoaded,
  wirePipeline,
} from '../helpers'

const { DATASET, JUDGE, EVAL } = PIPELINE_IDS

// The generic per-node secondary tabs (Details/Inputs/Outputs/Timing) + on-node run-time
// badge — verified in a real browser after a real (dry) run so the run store is populated.
test.describe('node I/O + timing tabs', () => {
  test('every node exposes Inputs/Outputs/Timing tabs and an on-node run-time badge', async ({ page }) => {
    await page.goto('/')
    await waitForPaletteLoaded(page)
    await addPipelineNodes(page)
    await page.getByRole('button', { name: 'Fit View' }).click()
    await wirePipeline(page)

    const runButton = page.getByRole('button', { name: /^Run(ning…)?$/ })
    await runButton.click()
    await expect(runButton).toHaveText('Run', { timeout: 15000 })

    // On-node elapsed time: after a run, every node shows its run time along the bottom
    // (dry-run still executes + times each node centrally).
    const datasetNode = page.getByTestId(`rf__node-${DATASET}`)
    await expect(datasetNode.locator('.rf-node-time-footer')).toBeVisible()

    // Open the Dataset node's secondary window — the tab strip must be present.
    await datasetNode.dblclick()
    const modal = page.locator('.modal-panel')
    await expect(modal).toBeVisible()
    for (const label of ['Details', 'Inputs', 'Outputs', 'Timing']) {
      await expect(modal.getByRole('tab', { name: label })).toBeVisible()
    }

    // Outputs tab: the Dataset node's own output sockets (samples + labels), populated.
    await modal.getByRole('tab', { name: 'Outputs' }).click()
    await expect(modal.locator('.io-socket-name', { hasText: 'samples' })).toBeVisible()
    await expect(modal.locator('.io-socket-name', { hasText: 'labels' })).toBeVisible()

    // Inputs tab: reconstructed raw_dataset input, marked fan-in (the tag now appears in both
    // the schema header and the value card, so match the first).
    await modal.getByRole('tab', { name: 'Inputs' }).click()
    await expect(modal.locator('.io-socket-name', { hasText: 'raw_dataset' })).toBeVisible()
    await expect(modal.getByText('fan-in').first()).toBeVisible()

    // Timing tab: both parts render — the system waterfall + this node's breakdown.
    await modal.getByRole('tab', { name: 'Timing' }).click()
    await expect(modal.getByText('System run waterfall')).toBeVisible()
    await expect(modal.getByText('This node — detailed breakdown')).toBeVisible()

    await page.getByRole('button', { name: 'Close' }).click()
    await expect(modal).toHaveCount(0)

    // The Judge node's Timing tab also shows both parts (its per-item breakdown appears
    // when it ran items; the two-part structure is always present regardless).
    await page.getByTestId(`rf__node-${JUDGE}`).dblclick()
    await modal.getByRole('tab', { name: 'Timing' }).click()
    await expect(modal.getByText('System run waterfall')).toBeVisible()
    await expect(modal.getByText('This node — detailed breakdown')).toBeVisible()
  })
})

// The Alignment Report node — reads the Eval node's metrics_report and frames it against the
// published VE-Bench baselines.
test.describe('Alignment Report node', () => {
  test('reads the Eval report and shows the VE-Bench baseline reference', async ({ page }) => {
    await page.goto('/')
    await waitForPaletteLoaded(page)
    await addPipelineNodes(page)
    await addNode(page, 'alignment_report') // -> alignment_report-7 (global id counter)
    await page.getByRole('button', { name: 'Fit View' }).click()
    await wirePipeline(page)
    // Eval's metrics_report output feeds the Alignment Report.
    await connectSockets(page, EVAL, 'metrics_report', 'alignment_report-7', 'metrics_report')

    const runButton = page.getByRole('button', { name: /^Run(ning…)?$/ })
    await runButton.click()
    await expect(runButton).toHaveText('Run', { timeout: 15000 })

    await page.getByTestId('rf__node-alignment_report-7').dblclick()
    const modal = page.locator('.modal-panel')
    await expect(modal).toBeVisible()
    // The published VE-Bench reference table always renders once the node has run.
    await expect(modal.getByText('VE-Bench published baselines (reference)')).toBeVisible()
    await expect(modal.getByRole('cell', { name: 'VE-Bench QA' })).toBeVisible()
    await page.getByRole('button', { name: 'Close' }).click()
  })
})

// The VE-Bench source node (fixture data provided by tests/e2e_fixture.py) — palette
// presence, wiring into a Dataset, a dry run, and its Outputs tab populating.
test.describe('VE-Bench source node', () => {
  test('lists in the palette, wires into a Dataset, and produces raw_dataset', async ({ page }) => {
    await page.goto('/')
    await waitForPaletteLoaded(page)

    // idCounter is global across node types, so the second node added is dataset-2.
    await addNode(page, 'vebench_source')
    await addNode(page, 'dataset')
    const veNode = page.getByTestId('rf__node-vebench_source-1')
    const dsNode = page.getByTestId('rf__node-dataset-2')
    await expect(veNode).toBeVisible()
    await expect(dsNode).toBeVisible()

    await page.getByRole('button', { name: 'Fit View' }).click()
    await dragConnect(
      page,
      page.locator('[data-nodeid="vebench_source-1"][data-handleid="raw_dataset"].source'),
      page.locator('[data-nodeid="dataset-2"][data-handleid="raw_dataset"].target'),
    )
    await expect(
      page.getByTestId('rf__edge-vebench_source-1:raw_dataset->dataset-2:raw_dataset'),
    ).toHaveCount(1)

    const runButton = page.getByRole('button', { name: /^Run(ning…)?$/ })
    await runButton.click()
    await expect(runButton).toHaveText('Run', { timeout: 15000 })

    // The VE-Bench source produced its raw_dataset (the 2 fixture items).
    await veNode.dblclick()
    const modal = page.locator('.modal-panel')
    await modal.getByRole('tab', { name: 'Outputs' }).click()
    await expect(modal.locator('.io-socket-name', { hasText: 'raw_dataset' })).toBeVisible()
    await expect(modal.getByText(/object · 2 keys/)).toBeVisible()
  })
})
