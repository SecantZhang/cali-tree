import { expect, test } from '@playwright/test'
import { waitForPaletteLoaded } from '../helpers'

test('workflow folders save, browse, load, and delete nested workflows', async ({ page }) => {
  await page.goto('/')
  await waitForPaletteLoaded(page)
  await page.getByRole('button', { name: 'Workflows', exact: true }).click()

  const workflowPath = `examples/edit-aware-${Date.now()}`
  const workflowName = workflowPath.split('/').at(-1)!
  await page.getByLabel('Workflow name or folder/name').fill(workflowPath)
  await page.getByRole('button', { name: 'Save current graph' }).click()

  const folder = page.locator('.workflow-folder', {
    has: page.locator('summary', { hasText: 'examples' }),
  })
  await expect(folder).toBeVisible()
  const row = folder.locator('.workflow-item', { hasText: workflowName })
  await expect(row).toBeVisible()
  await expect(row).toHaveAttribute('title', workflowPath)

  await row.getByRole('button', { name: 'Load' }).click()
  const matchingTabs = page.locator('.tab-item', { hasText: workflowPath })
  // Saving names the current tab; loading intentionally opens an independent second copy.
  await expect(matchingTabs).toHaveCount(2)
  await expect(matchingTabs.last()).toHaveClass(/active/)

  await page.getByRole('button', { name: 'Workflows', exact: true }).click()
  await folder
    .locator('.workflow-item', { hasText: workflowName })
    .getByRole('button', { name: 'Delete' })
    .click()
  await expect(folder.locator('.workflow-item', { hasText: workflowName })).toHaveCount(0)
})
