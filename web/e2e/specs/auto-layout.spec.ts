import { expect, test } from '@playwright/test'
import { addPipelineNodes, PIPELINE_IDS, waitForPaletteLoaded, wirePipeline } from '../helpers'

test('auto layout arranges a workflow by topological depth without node overlap', async ({ page }) => {
  await page.goto('/')
  await waitForPaletteLoaded(page)

  await addPipelineNodes(page)
  await page.getByRole('button', { name: 'Fit View' }).click()
  await wirePipeline(page)

  await page.getByRole('button', { name: 'Auto layout' }).click()
  await page.waitForTimeout(450) // fitView animation

  const boxes = await Promise.all(
    Object.values(PIPELINE_IDS).map(async (id) => {
      const box = await page.getByTestId(`rf__node-${id}`).boundingBox()
      if (!box) throw new Error(`missing box for ${id}`)
      return box
    }),
  )
  const [peanut, dataset, engine, prompt, judge, evaluation] = boxes
  expect(Math.abs(peanut.x - engine.x)).toBeLessThan(2)
  expect(Math.abs(peanut.x - prompt.x)).toBeLessThan(2)
  expect(dataset.x).toBeGreaterThan(peanut.x + peanut.width)
  expect(judge.x).toBeGreaterThan(dataset.x + dataset.width)
  expect(evaluation.x).toBeGreaterThan(judge.x + judge.width)

  const roots = [peanut, engine, prompt].sort((a, b) => a.y - b.y)
  expect(roots[1].y).toBeGreaterThanOrEqual(roots[0].y + roots[0].height)
  expect(roots[2].y).toBeGreaterThanOrEqual(roots[1].y + roots[1].height)
})
