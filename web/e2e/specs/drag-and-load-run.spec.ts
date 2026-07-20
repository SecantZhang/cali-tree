import { expect, test } from '@playwright/test'
import {
  addPipelineNodes,
  PIPELINE_IDS,
  paletteItem,
  waitForPaletteLoaded,
  wirePipeline,
} from '../helpers'

const { EVAL } = PIPELINE_IDS

// Feature A — palette → canvas drag-and-drop. Native HTML5 DnD carries the node type on a
// DataTransfer (mouse-based dragTo would never populate it), so drive dragstart/drop with a
// shared DataTransfer handle and a real drop point; the canvas onDrop projects screen→flow
// coords and adds the node there. This is the only layer that exercises the real
// dataTransfer.getData path + React Flow's real screenToFlowPosition.
test.describe('palette drag-and-drop', () => {
  test('dragging a palette item onto the canvas adds that node at the drop point', async ({ page }) => {
    await page.goto('/')
    await waitForPaletteLoaded(page)

    // Starts empty — no eval node yet.
    await expect(page.getByTestId('rf__node-eval-1')).toHaveCount(0)

    const dt = await page.evaluateHandle(() => new DataTransfer())
    await paletteItem(page, 'eval').dispatchEvent('dragstart', { dataTransfer: dt })

    const flow = page.locator('.react-flow')
    const box = await flow.boundingBox()
    if (!box) throw new Error('no react-flow bounding box')
    const dropX = box.x + box.width * 0.5
    const dropY = box.y + box.height * 0.5
    await flow.dispatchEvent('dragover', { dataTransfer: dt, clientX: dropX, clientY: dropY })
    await flow.dispatchEvent('drop', { dataTransfer: dt, clientX: dropX, clientY: dropY })

    // First node added this session → the deterministic id is eval-1 (idCounter resets per
    // page load). It exists and is placed near the drop point, not on the default grid.
    const node = page.getByTestId('rf__node-eval-1')
    await expect(node).toBeVisible()
    const nodeBox = await node.boundingBox()
    if (!nodeBox) throw new Error('dropped node has no bounding box')
    // The node's top-left lands within a generous radius of the drop point (allowing for
    // node size + fitView zoom); the point is it followed the cursor, not the grid origin.
    expect(Math.abs(nodeBox.x - dropX)).toBeLessThan(260)
    expect(Math.abs(nodeBox.y - dropY)).toBeLessThan(260)
  })
})

// Feature B — load a past run from disk. Run a dry-run, then reopen it from the Runs tab and
// assert the graph + per-node statuses + the Eval node's report reconstruct from disk. The
// E2E backend uses a fresh temp logs dir and the suite is serial (workers:1), so the run we
// just created is the newest on disk — the first entry in the Runs list.
test.describe('load a past run', () => {
  test('a completed dry-run reopens from the Runs tab with graph + statuses + outputs', async ({ page }) => {
    await page.goto('/')
    await waitForPaletteLoaded(page)

    await addPipelineNodes(page)
    await page.getByRole('button', { name: 'Fit View' }).click()
    await wirePipeline(page)

    const runButton = page.getByRole('button', { name: /^Run(ning…)?$/ })
    await runButton.click()
    await expect(runButton).toHaveText('Run', { timeout: 10000 })

    // Switch to the Runs tab; the newest disk run (the one we just finished) is first.
    await page.getByRole('button', { name: 'Runs' }).click()
    const firstRun = page.locator('.run-item').first()
    await expect(firstRun).toBeVisible({ timeout: 10000 })
    // A completed run is done, so it is NOT offered a Resume button (Resume gates on
    // error/stopped/interrupted) — but it can always be Opened.
    await expect(firstRun.locator('.run-status-tag')).toHaveText('done')
    await expect(firstRun.getByRole('button', { name: 'Resume' })).toHaveCount(0)
    await firstRun.getByRole('button', { name: 'Open' }).click()

    // Opening spawns a fresh tab whose graph is reconstructed from workflow_graph.json (same
    // node ids) and whose statuses + Eval outputs hydrate via the disk-fallback GET /runs/{id}.
    const evalNode = page.getByTestId(`rf__node-${EVAL}`)
    await expect(evalNode).toBeVisible({ timeout: 10000 })
    await expect(evalNode.locator('.status-dot.status-done')).toBeVisible()

    // The Eval report reconstructs (dry-run produced 0 aligned items, but the report is
    // well-formed and recovered from the persisted run_results.json).
    await evalNode.dblclick()
    const modal = page.locator('.modal-panel')
    await expect(modal).toBeVisible()
    await expect(modal.getByText('0 aligned item(s).')).toBeVisible()
    await page.getByRole('button', { name: 'Close' }).click()
    await expect(modal).toHaveCount(0)
  })
})
