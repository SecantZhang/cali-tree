import { expect, test } from '@playwright/test'
import { addPipelineNodes, PIPELINE_IDS, waitForPaletteLoaded, wirePipeline } from '../helpers'

const { PROMPT, JUDGE, EVAL } = PIPELINE_IDS

test.describe('streaming batch-eval', () => {
  test('a batch_size=1 Judge Node streams a live Eval preview over the run websocket before the run finishes', async ({
    page,
  }) => {
    await page.goto('/')
    await waitForPaletteLoaded(page)

    // Capture every raw WS frame the run socket carries, so the assertions below can
    // verify the actual streamed event *order* (partial before run_complete) directly —
    // racing the UI's own render against the mock gateway's per-call delay for a
    // single-item window is far too timing-sensitive to assert on reliably, but the wire
    // protocol itself is not.
    const frames: Array<Record<string, unknown>> = []
    page.on('websocket', (ws) => {
      ws.on('framereceived', (frame) => {
        try {
          frames.push(JSON.parse(String(frame.payload)))
        } catch {
          // Non-JSON frames (there shouldn't be any) are simply not relevant here.
        }
      })
    })

    await addPipelineNodes(page)

    const promptNode = page.getByTestId(`rf__node-${PROMPT}`)
    const judgeNode = page.getByTestId(`rf__node-${JUDGE}`)
    const evalNode = page.getByTestId(`rf__node-${EVAL}`)
    await page.getByRole('button', { name: 'Fit View' }).click()

    // M3 preset (text modality, and the one metric with a human-annotation crosswalk so the
    // Eval preview has aligned rows) -> 2 sequential mock-gateway calls (concurrency defaults
    // to 1), one per fixture item, at the mock's ~200ms per-call delay. batch_size defaults
    // to 1, so the first fully-judged item triggers a preview well before the run finishes.
    await promptNode.locator('.param-row', { hasText: 'preset' }).locator('select').selectOption('M3')
    await expect(judgeNode.locator('.param-row', { hasText: 'batch_size' }).locator('input[type="text"]'))
      .toHaveValue('1')
    await judgeNode.getByRole('button', { name: 'Collapse node' }).click()

    await wirePipeline(page)

    await page.locator('.dry-run-toggle input[type="checkbox"]').uncheck()
    page.once('dialog', (dialog) => dialog.accept())
    await page.getByRole('button', { name: /^Run(ning…)?$/ }).click()
    // Confirm the run genuinely started before waiting for it to finish — `toHaveText`
    // matches the moment ANY poll observes the target text, so waiting straight for 'Run'
    // here could spuriously match the button's *pre-click* state a few ms in, before it
    // ever flips to 'Running…' at all (a real race found while writing this test).
    await expect(page.getByRole('button', { name: 'Running…' })).toBeVisible()
    await expect(page.getByRole('button', { name: /^Run(ning…)?$/ })).toHaveText('Run', { timeout: 20000 })

    const partialIdx = frames.findIndex((f) => f.type === 'partial_result' && f.node_id === EVAL)
    const completeIdx = frames.findIndex((f) => f.type === 'run_complete')
    expect(partialIdx, 'expected a partial_result frame for the Eval node').toBeGreaterThanOrEqual(0)
    expect(completeIdx, 'expected a run_complete frame').toBeGreaterThanOrEqual(0)
    expect(partialIdx).toBeLessThan(completeIdx) // streamed *before* the run finished, not after

    const partialFrame = frames[partialIdx] as { outputs: { metrics_report: { n_items: number } } }
    // The first fully-judged item triggers the preview -> exactly 1 aligned item, not the
    // eventual authoritative 2 (proof it's a genuinely partial, not final, snapshot).
    expect(partialFrame.outputs.metrics_report.n_items).toBe(1)

    // The Judge Node's own in-flight snapshot is a *separate* partial_result event (the
    // executor's on_batch closure emits one for the calling node itself, independent of
    // the downstream-preview mechanism above) — this is what lets the Judge Node's own
    // secondary tab render a live-updating histogram, not just downstream nodes.
    const judgePartialIdx = frames.findIndex((f) => f.type === 'partial_result' && f.node_id === JUDGE)
    expect(judgePartialIdx, 'expected a partial_result frame for the Judge node itself').toBeGreaterThanOrEqual(0)
    expect(judgePartialIdx).toBeLessThan(completeIdx)
    const judgePartialFrame = frames[judgePartialIdx] as { outputs: { judge_result: Record<string, unknown> } }
    // Same "first fully-judged item only" partial-ness check as Eval's preview above.
    expect(Object.keys(judgePartialFrame.outputs.judge_result)).toHaveLength(1)

    // The browser-rendered final state (checked only once the run has fully settled, so
    // this part is not timing-sensitive) reflects the real, authoritative result.
    await evalNode.dblclick()
    const evalModal = page.locator('.modal-panel')
    await expect(evalModal.locator('p', { hasText: 'aligned item(s).' })).toHaveText('2 aligned item(s).')
    await expect(evalModal.locator('.empty-hint', { hasText: 'Live preview' })).toHaveCount(0)
  })
})
