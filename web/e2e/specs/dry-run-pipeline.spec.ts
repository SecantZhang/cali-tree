import { expect, test } from '@playwright/test'
import { addNode, dragConnect, waitForPaletteLoaded } from '../helpers'

// addNode's module-level id counter (graphStore.ts) resets on every fresh page load, so
// clicking peanut_source, dataset, lm_engine, judge_text, eval in that order
// deterministically yields these ids. Peanut Source's raw_dataset must pass through a
// Dataset node before it can reach Judge (raw_dataset is a distinct socket type,
// specifically so sampling is always an explicit step) — Dataset also joins matching
// human-annotation labels by item id for exactly the items it sampled, and feeds Eval's
// `labels` directly from that same node. `engine_config` is a required input even in
// dry-run mode (the check happens before the dry-run branch), so an LM Engine node must
// be wired regardless of whether this run ever makes a real gateway call.
const PEANUT_SOURCE = 'peanut_source-1'
const DATASET = 'dataset-2'
const LM_ENGINE = 'lm_engine-3'
const JUDGE = 'judge_text-4'
const EVAL = 'eval-5'

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
  test('runs a fully wired 5-node graph in dry-run mode end to end', async ({ page }) => {
    await page.goto('/')
    await waitForPaletteLoaded(page)

    await addNode(page, 'peanut_source')
    await addNode(page, 'dataset')
    await addNode(page, 'lm_engine')
    await addNode(page, 'judge_text')
    await addNode(page, 'eval')

    const peanutSourceNode = page.getByTestId(`rf__node-${PEANUT_SOURCE}`)
    const datasetNode = page.getByTestId(`rf__node-${DATASET}`)
    const lmEngineNode = page.getByTestId(`rf__node-${LM_ENGINE}`)
    const judgeNode = page.getByTestId(`rf__node-${JUDGE}`)
    const evalNode = page.getByTestId(`rf__node-${EVAL}`)
    await expect(peanutSourceNode).toBeVisible()
    await expect(datasetNode).toBeVisible()
    await expect(lmEngineNode).toBeVisible()
    await expect(judgeNode).toBeVisible()
    await expect(evalNode).toBeVisible()

    // Fit View before collapsing (not after) — matching the other specs in this suite;
    // computing the fit against Judge's still-expanded height first, then collapsing,
    // avoids a zoom level that leaves adjacent nodes' connecting edges too close together
    // to render with a real (non-degenerate) bounding box.
    await page.getByRole('button', { name: 'Fit View' }).click()
    await judgeNode.getByRole('button', { name: 'Collapse node' }).click()

    // Wire the full pipeline: source -> dataset -> judge -> eval, plus Dataset's own
    // `labels` output straight to eval (the Eval node needs both a judge_result AND
    // human labels to align).
    await connect(page, PEANUT_SOURCE, 'raw_dataset', DATASET, 'raw_dataset')
    await connect(page, DATASET, 'dataset', JUDGE, 'dataset')
    await connect(page, LM_ENGINE, 'engine_config', JUDGE, 'engine_config')
    await connect(page, JUDGE, 'judge_result', EVAL, 'judge_result_text')
    await connect(page, DATASET, 'labels', EVAL, 'labels')
    await expect(page.getByTestId(`rf__edge-${PEANUT_SOURCE}:raw_dataset->${DATASET}:raw_dataset`)).toHaveCount(1)
    await expect(page.getByTestId(`rf__edge-${DATASET}:dataset->${JUDGE}:dataset`)).toHaveCount(1)
    await expect(page.getByTestId(`rf__edge-${LM_ENGINE}:engine_config->${JUDGE}:engine_config`)).toHaveCount(1)
    await expect(page.getByTestId(`rf__edge-${JUDGE}:judge_result->${EVAL}:judge_result_text`)).toHaveCount(1)
    await expect(page.getByTestId(`rf__edge-${DATASET}:labels->${EVAL}:labels`)).toHaveCount(1)

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

    for (const node of [peanutSourceNode, datasetNode, lmEngineNode, judgeNode, evalNode]) {
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
