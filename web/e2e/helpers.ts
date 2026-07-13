import type { Locator, Page } from '@playwright/test'

export type NodeTypeName =
  | 'peanut_source' | 'dataset' | 'preprocessing' | 'lm_engine'
  | 'judge_prompt' | 'judge' | 'eval' | 'cl_adversarial'

// `page.getByText('dataset')` is a case-insensitive substring match by default, which
// also matches unrelated static UI text ("Datasets" tab label, "VEJudge" title) —
// scoping to the actual palette item first avoids that false-positive class of bug.
// Uses an exact (anchored) match: 'judge' would otherwise substring-match 'judge_prompt'.
export function paletteItem(page: Page, nodeType: NodeTypeName): Locator {
  return page.locator('.node-palette-item').filter({ hasText: new RegExp(`^${nodeType}$`) })
}

export async function addNode(page: Page, nodeType: NodeTypeName): Promise<void> {
  await paletteItem(page, nodeType).click()
}

export async function waitForPaletteLoaded(page: Page): Promise<void> {
  const types: NodeTypeName[] = [
    'peanut_source', 'dataset', 'preprocessing', 'lm_engine',
    'judge_prompt', 'judge', 'eval',
  ]
  await paletteItem(page, types[0]).waitFor({ state: 'visible', timeout: 10000 })
  for (const t of types.slice(1)) {
    await paletteItem(page, t).waitFor({ state: 'visible' })
  }
}

// React Flow renders a full-canvas `.react-flow__pane` overlay while a connection drag is
// in progress, which fails Locator.dragTo's final actionability re-check on the target
// handle (it sees the pane on top, not the handle). Driving raw page.mouse events instead
// skips that re-check — React Flow itself only cares about document-level pointermove/up.
export async function dragConnect(page: Page, source: Locator, target: Locator): Promise<void> {
  // React Flow renders a full-canvas `.react-flow__pane` overlay while a connection drag is
  // in progress, which fails Locator.hover/dragTo's actionability re-check on the target
  // handle (it sees the pane on top, not the handle) even though React Flow itself resolves
  // the hovered handle from raw pointer coordinates, not DOM hit-testing — so drive raw
  // page.mouse events computed from boundingBox() instead of any locator-based hover/click.
  const sourceBox = await source.boundingBox()
  const targetBox = await target.boundingBox()
  if (!sourceBox || !targetBox) throw new Error('dragConnect: handle has no bounding box')

  const from = { x: sourceBox.x + sourceBox.width / 2, y: sourceBox.y + sourceBox.height / 2 }
  const to = { x: targetBox.x + targetBox.width / 2, y: targetBox.y + targetBox.height / 2 }

  await page.mouse.move(from.x, from.y)
  await page.mouse.down()
  await page.mouse.move((from.x + to.x) / 2, (from.y + to.y) / 2, { steps: 10 })
  await page.mouse.move(to.x, to.y, { steps: 10 })
  // React Flow's connection end-handler resolves the hovered handle from the DOM on the
  // next frame after the final pointermove, not synchronously — give it a tick before up.
  await page.waitForTimeout(100)
  await page.mouse.up()
}

// Connect a source node's output socket to a target node's input socket by handle id.
export async function connectSockets(
  page: Page,
  sourceNodeId: string, sourceHandleId: string,
  targetNodeId: string, targetHandleId: string,
): Promise<void> {
  const source = page.locator(`[data-nodeid="${sourceNodeId}"][data-handleid="${sourceHandleId}"].source`)
  const target = page.locator(`[data-nodeid="${targetNodeId}"][data-handleid="${targetHandleId}"].target`)
  await dragConnect(page, source, target)
}

// The canonical per-metric pipeline: Peanut Source -> Dataset -> Judge (with an LM Engine +
// a Judge Prompt preset) -> Eval, plus Dataset.labels -> Eval. addNode's id counter resets
// each page load, so clicking in this order yields these fixed ids. Returns the ids so a
// spec can assert on specific nodes.
export const PIPELINE_IDS = {
  PEANUT_SOURCE: 'peanut_source-1',
  DATASET: 'dataset-2',
  LM_ENGINE: 'lm_engine-3',
  PROMPT: 'judge_prompt-4',
  JUDGE: 'judge-5',
  EVAL: 'eval-6',
} as const

export async function addPipelineNodes(page: Page): Promise<void> {
  await addNode(page, 'peanut_source')
  await addNode(page, 'dataset')
  await addNode(page, 'lm_engine')
  await addNode(page, 'judge_prompt')
  await addNode(page, 'judge')
  await addNode(page, 'eval')
}

export async function wirePipeline(page: Page): Promise<void> {
  const { PEANUT_SOURCE, DATASET, LM_ENGINE, PROMPT, JUDGE, EVAL } = PIPELINE_IDS
  await connectSockets(page, PEANUT_SOURCE, 'raw_dataset', DATASET, 'raw_dataset')
  await connectSockets(page, DATASET, 'samples', JUDGE, 'samples')
  await connectSockets(page, LM_ENGINE, 'engine_config', JUDGE, 'engine_config')
  await connectSockets(page, PROMPT, 'judge_spec', JUDGE, 'judge_spec')
  await connectSockets(page, JUDGE, 'judge_result', EVAL, 'judge_result')
  await connectSockets(page, DATASET, 'labels', EVAL, 'labels')
}
