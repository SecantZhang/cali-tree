import type { Locator, Page } from '@playwright/test'

export type NodeTypeName =
  | 'peanut_source' | 'dataset' | 'preprocessing' | 'lm_engine'
  | 'judge_text' | 'judge_video' | 'eval'

// `page.getByText('dataset')` is a case-insensitive substring match by default, which
// also matches unrelated static UI text ("Datasets" tab label, "VEJudge" title) —
// scoping to the actual palette item first avoids that false-positive class of bug.
// Uses an exact match: 'judge_text'/'judge_video' would otherwise substring-match each
// other.
export function paletteItem(page: Page, nodeType: NodeTypeName): Locator {
  return page.locator('.node-palette-item').filter({ hasText: new RegExp(`^${nodeType}$`) })
}

export async function addNode(page: Page, nodeType: NodeTypeName): Promise<void> {
  await paletteItem(page, nodeType).click()
}

export async function waitForPaletteLoaded(page: Page): Promise<void> {
  const types: NodeTypeName[] = [
    'peanut_source', 'dataset', 'preprocessing', 'lm_engine',
    'judge_text', 'judge_video', 'eval',
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
