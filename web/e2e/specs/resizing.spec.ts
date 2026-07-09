import { expect, test } from '@playwright/test'
import { addNode, waitForPaletteLoaded } from '../helpers'

async function dragBy(page: import('@playwright/test').Page, x: number, y: number, dx: number, dy: number) {
  await page.mouse.move(x, y)
  await page.mouse.down()
  await page.mouse.move(x + dx, y + dy, { steps: 8 })
  await page.mouse.up()
}

test.describe('resizable panels and nodes', () => {
  test('dragging the left-panel handle resizes it and persists across a reload', async ({
    page,
  }) => {
    await page.goto('/')
    await waitForPaletteLoaded(page)

    const leftPanel = page.locator('.left-panel')
    const before = await leftPanel.boundingBox()
    expect(before).toBeTruthy()

    const handle = page.locator('.resize-handle-vertical').first()
    const handleBox = await handle.boundingBox()
    expect(handleBox).toBeTruthy()
    const hx = handleBox!.x + handleBox!.width / 2
    const hy = handleBox!.y + handleBox!.height / 2
    await dragBy(page, hx, hy, 80, 0)

    const after = await leftPanel.boundingBox()
    expect(after!.width).toBeGreaterThan(before!.width + 60)

    // Persisted via localStorage (prefsStore) — survives a full page reload.
    await page.reload()
    await waitForPaletteLoaded(page)
    const afterReload = await page.locator('.left-panel').boundingBox()
    expect(afterReload!.width).toBeCloseTo(after!.width, 0)
  })

  test('dragging a bottom-panel handle resizes the console', async ({ page }) => {
    await page.goto('/')
    await waitForPaletteLoaded(page)

    const bottomPanel = page.locator('.bottom-panel')
    const before = await bottomPanel.boundingBox()

    const handle = page.locator('.resize-handle-horizontal')
    const handleBox = await handle.boundingBox()
    const hx = handleBox!.x + handleBox!.width / 2
    const hy = handleBox!.y + handleBox!.height / 2
    // Dragging the handle up increases the bottom panel's height.
    await dragBy(page, hx, hy, 0, -60)

    const after = await bottomPanel.boundingBox()
    expect(after!.height).toBeGreaterThan(before!.height + 40)
  })

  test('selecting a node reveals resize handles, and dragging one resizes the node', async ({
    page,
  }) => {
    await page.goto('/')
    await waitForPaletteLoaded(page)
    await addNode(page, 'judge_text')

    const node = page.getByTestId('rf__node-judge_text-1')
    await expect(node).toBeVisible()
    // addNode leaves the new node selected already, but click it explicitly so this test
    // doesn't depend on that incidental behavior.
    await node.click()

    // Move the node up-and-left first — with only 2 params now (metrics, batch_size;
    // engine config moved to a separate LM Engine Node), the node is short enough that its
    // default grid position puts its bottom-right corner directly under the fixed-position
    // MiniMap panel, which visually sits on top of (and intercepts pointer events meant
    // for) the resize handle underneath it — a real rendering interaction, not a product
    // bug, found while updating this test for that param-count change.
    const headerBox = await node.locator('.rf-node-header').boundingBox()
    await dragBy(page, headerBox!.x + headerBox!.width / 2, headerBox!.y + headerBox!.height / 2, -150, -60)

    const bottomRightHandle = node.locator('.rf-node-resize-handle.bottom.right')
    await expect(bottomRightHandle).toBeVisible()

    const before = await node.boundingBox()
    const handleBox = await bottomRightHandle.boundingBox()
    const hx = handleBox!.x + handleBox!.width / 2
    const hy = handleBox!.y + handleBox!.height / 2
    await dragBy(page, hx, hy, 100, 80)

    const after = await node.boundingBox()
    expect(after!.width).toBeGreaterThan(before!.width + 60)
    expect(after!.height).toBeGreaterThan(before!.height + 60)
  })

  test('deselecting a node hides its resize handles', async ({ page }) => {
    await page.goto('/')
    await waitForPaletteLoaded(page)
    await addNode(page, 'judge_text')

    const node = page.getByTestId('rf__node-judge_text-1')
    await node.click()
    await expect(node.locator('.rf-node-resize-handle.bottom.right')).toBeVisible()

    await page.locator('.canvas-area').click({ position: { x: 10, y: 10 } })
    await expect(node.locator('.rf-node-resize-handle.bottom.right')).toBeHidden()
  })
})
