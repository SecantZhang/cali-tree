import { expect, test } from '@playwright/test'
import { addPipelineNodes, PIPELINE_IDS, waitForPaletteLoaded, wirePipeline } from '../helpers'

const { JUDGE } = PIPELINE_IDS

test.describe('path highlight', () => {
  test('selecting a node highlights the full root→leaf path through it', async ({ page }) => {
    await page.goto('/')
    await waitForPaletteLoaded(page)

    await addPipelineNodes(page)
    await page.getByRole('button', { name: 'Fit View' }).click()
    await wirePipeline(page)

    // Nothing highlighted before any selection.
    await expect(page.locator('.react-flow__edge.edge-highlight')).toHaveCount(0)

    // Selecting the Judge highlights the edges on its up+down path (dataset→judge,
    // prompt→judge, engine→judge, peanut→dataset, judge→eval, dataset→eval).
    await page.getByTestId(`rf__node-${JUDGE}`).click()
    const highlighted = page.locator('.react-flow__edge.edge-highlight')
    await expect(async () => {
      expect(await highlighted.count()).toBeGreaterThan(1)
    }).toPass({ timeout: 5000 })

    // Clicking empty canvas clears the selection and the highlight.
    await page.locator('.react-flow__pane').click({ position: { x: 20, y: 20 } })
    await expect(page.locator('.react-flow__edge.edge-highlight')).toHaveCount(0)
  })
})
