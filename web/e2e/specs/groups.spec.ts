import { expect, test } from '@playwright/test'
import { waitForPaletteLoaded } from '../helpers'

test.describe('canvas groups', () => {
  test('right-click adds a group; renaming it persists across a save + reload', async ({ page }) => {
    await page.goto('/')
    await waitForPaletteLoaded(page)

    // Right-click empty canvas -> "Add group here".
    await page.locator('.react-flow__pane').click({ button: 'right', position: { x: 320, y: 260 } })
    await page.getByRole('button', { name: /Add group here/ }).click()

    const group = page.locator('.rf-group')
    await expect(group).toHaveCount(1)
    await group.locator('.rf-group-title').fill('My Group')

    // Save the workflow, reload (canvas is in-memory only), and load it back.
    const name = `groups-e2e-${Date.now()}`
    await page.getByRole('button', { name: 'Workflows', exact: true }).click()
    await page.getByPlaceholder('workflow name').fill(name)
    await page.getByRole('button', { name: 'Save current graph' }).click()
    await expect(page.locator('.workflow-item', { hasText: name })).toBeVisible()

    await page.reload()
    await waitForPaletteLoaded(page)
    await expect(page.locator('.rf-group')).toHaveCount(0)

    await page.getByRole('button', { name: 'Workflows', exact: true }).click()
    await page.locator('.workflow-item', { hasText: name }).getByRole('button', { name: 'Load' }).click()

    await expect(page.locator('.rf-group')).toHaveCount(1)
    await expect(page.locator('.rf-group-title')).toHaveValue('My Group')
  })

  test('a group can be removed via its right-click menu', async ({ page }) => {
    await page.goto('/')
    await waitForPaletteLoaded(page)

    await page.locator('.react-flow__pane').click({ button: 'right', position: { x: 30, y: 30 } })
    await page.getByRole('button', { name: /Add group here/ }).click()
    const group = page.locator('.rf-group')
    await expect(group).toHaveCount(1)

    // Right-click the group itself → "Remove group".
    await group.click({ button: 'right' })
    await page.getByRole('button', { name: /Remove group/ }).click()
    await expect(group).toHaveCount(0)
  })
})
