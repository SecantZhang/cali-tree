import { expect, test } from '@playwright/test'
import { addNode, dragConnect, waitForPaletteLoaded } from '../helpers'

// addNode's module-level id counter (graphStore.ts) resets on every fresh page load, so
// clicking dataset, dataset, judge, eval in that order deterministically yields these ids.
// A Dataset Node only ever populates ONE of its two output sockets per run, chosen by its
// `loader` param (see dataset_node.py's docstring) — so getting real data into both of
// Eval's inputs needs two Dataset nodes: one peanut_eval (-> Judge's `dataset`) and one
// human_annotations (-> Eval's `labels`), same shape as the `base_benchmark` preset.
const PEANUT_DATASET = 'dataset-1'
const LABELS_DATASET = 'dataset-2'
const JUDGE = 'judge-3'
const EVAL = 'eval-4'

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

test.describe('dry-run pipeline', () => {
  test('runs a fully wired 4-node graph in dry-run mode end to end', async ({ page }) => {
    await page.goto('/')
    await waitForPaletteLoaded(page)

    await addNode(page, 'dataset')
    await addNode(page, 'dataset')
    await addNode(page, 'judge')
    await addNode(page, 'eval')

    const peanutDatasetNode = page.getByTestId(`rf__node-${PEANUT_DATASET}`)
    const labelsDatasetNode = page.getByTestId(`rf__node-${LABELS_DATASET}`)
    const judgeNode = page.getByTestId(`rf__node-${JUDGE}`)
    const evalNode = page.getByTestId(`rf__node-${EVAL}`)
    await expect(peanutDatasetNode).toBeVisible()
    await expect(labelsDatasetNode).toBeVisible()
    await expect(judgeNode).toBeVisible()
    await expect(evalNode).toBeVisible()

    await page.getByRole('button', { name: 'Fit View' }).click()

    // Second Dataset node switches to the human_annotations loader so it actually produces
    // a `labels` output (the default peanut_eval loader only ever produces `dataset`).
    await labelsDatasetNode.locator('.param-row', { hasText: 'loader' }).locator('select').selectOption('human_annotations')

    // Wire the full pipeline: peanut dataset -> judge -> eval, plus the labels dataset
    // straight to eval (the Eval node needs both a judge_result AND human labels to align).
    await connect(page, PEANUT_DATASET, 'dataset', JUDGE, 'dataset')
    await connect(page, JUDGE, 'judge_result', EVAL, 'judge_result')
    await connect(page, LABELS_DATASET, 'labels', EVAL, 'labels')
    await expect(page.getByTestId(`rf__edge-${PEANUT_DATASET}:dataset->${JUDGE}:dataset`)).toBeVisible()
    await expect(page.getByTestId(`rf__edge-${JUDGE}:judge_result->${EVAL}:judge_result`)).toBeVisible()
    await expect(page.getByTestId(`rf__edge-${LABELS_DATASET}:labels->${EVAL}:labels`)).toBeVisible()

    // Dry run is on by default — no confirm dialog, no gateway calls.
    await expect(page.locator('.dry-run-toggle input[type="checkbox"]')).toBeChecked()

    const runButton = page.getByRole('button', { name: /^Run(ning…)?$/ })
    await runButton.click()

    // The 3 progress bars (interface.md's Run controls): overall workflow progress and the
    // currently-running node's own bar, both in the top bar, plus the per-node bar on the
    // canvas — all only render while status === 'running', so this is a best-effort catch of
    // a run that may finish in well under a polling interval on a tiny dry-run graph.
    const runProgress = page.locator('.run-progress')
    await runProgress
      .waitFor({ state: 'visible', timeout: 2000 })
      .catch(() => {
        // A dry run over the tiny fixture dataset can complete before the first poll — that's
        // a legitimate outcome, not a bug; the real assertion is the end state below.
      })

    await expect(runButton).toHaveText('Run', { timeout: 10000 })
    await expect(runProgress).toHaveCount(0)

    for (const node of [peanutDatasetNode, labelsDatasetNode, judgeNode, evalNode]) {
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
