import { expect, test, type Page } from '@playwright/test'

test.beforeEach(async ({ page }) => {
  await page.addInitScript(() => {
    sessionStorage.setItem('pilot-token', 'local-picker-test-session')
    localStorage.clear()
  })
  await page.goto('/')
  await expect(page.getByRole('heading', { name: 'Recent projects' })).toBeVisible()
})

async function fixtureFolder(page: Page) {
  const dialog = page.getByTestId('file-picker')
  await dialog.locator('[data-location-kind=library]').click()
  await dialog.getByText('Picker fixtures', { exact: true }).click()
  return dialog
}

test('opens an existing project entirely through folder clicks', async ({ page }) => {
  await page.getByRole('button', { name: 'Open project', exact: true }).click()
  await page.getByRole('button', { name: 'Browse: Project directory', exact: true }).click()
  const dialog = await fixtureFolder(page)
  await dialog.getByText('Existing Project', { exact: true }).click()
  await dialog.getByRole('button', { name: 'Use selection', exact: true }).click()
  await expect(dialog).not.toBeVisible()
  await expect(page.getByLabel('Project directory', { exact: true })).toHaveValue(/\/Existing Project$/)
  await page.getByRole('button', { name: 'Open', exact: true }).click()
  await expect(page.locator('.project-name')).toHaveText('Picker existing')
})

test('creates a new project below the chosen parent and keeps the dialog inside the viewport', async ({ page }, info) => {
  await page.getByRole('button', { name: 'New project', exact: true }).last().click()
  await page.getByLabel('Project name', { exact: true }).fill(`Picker ${info.project.name}`)
  await page.getByRole('button', { name: 'Browse: Project folder', exact: true }).click()
  const dialog = await fixtureFolder(page)
  const name = `新工程 ${info.project.name}-${Date.now()}`
  await dialog.getByLabel('New project folder name (optional)', { exact: true }).fill(name)
  await expect(dialog.getByText('Selected path:', { exact: false })).toContainText(name)
  const bounds = await dialog.boundingBox()
  expect(bounds!.x).toBeGreaterThanOrEqual(0)
  expect(bounds!.y).toBeGreaterThanOrEqual(0)
  expect(bounds!.x + bounds!.width).toBeLessThanOrEqual(1366)
  expect(bounds!.y + bounds!.height).toBeLessThanOrEqual(768)
  await page.screenshot({ path: info.outputPath('file-picker.png'), animations: 'disabled' })
  await dialog.getByRole('button', { name: 'Use selection', exact: true }).click()
  await page.getByRole('button', { name: 'Create project', exact: true }).click()
  await expect(page.locator('.project-name')).toHaveText(`Picker ${info.project.name}`)
})

test('selects multiple data references, filters names, shows hidden folders and cancels without changes', async ({ page }) => {
  await page.getByRole('button', { name: /Picker existing/ }).click()
  await page.getByRole('button', { name: 'Go to Data', exact: true }).click()
  await page.getByRole('button', { name: /Browse: Input files or SAFE folders/ }).click()
  const dialog = await fixtureFolder(page)
  await dialog.getByRole('checkbox', { name: 'Select scene.h5', exact: true }).check()
  await dialog.getByRole('checkbox', { name: 'Select scene.SAFE', exact: true }).check()
  await dialog.getByLabel('Filter this folder', { exact: true }).fill('目录')
  await expect(dialog.locator('.picker-entries').getByText('scene.h5', { exact: true })).not.toBeVisible()
  await expect(dialog.locator('.picker-entries').getByText('目录 空格', { exact: true })).toBeVisible()
  await dialog.getByLabel('Filter this folder', { exact: true }).fill('')
  await dialog.getByRole('checkbox', { name: 'Hidden files', exact: true }).check()
  await expect(dialog.locator('.picker-entries').getByText('.hidden', { exact: true })).toBeVisible()
  await dialog.getByRole('button', { name: 'Use selection', exact: true }).click()
  const field = page.getByLabel('Input files or SAFE folders · one per line', { exact: true })
  const value = await field.inputValue()
  expect(value).toMatch(/scene.h5\n.*scene.SAFE$/)
  await page.getByRole('button', { name: /Browse: Input files or SAFE folders/ }).click()
  await page.getByTestId('file-picker').getByRole('button', { name: 'Cancel', exact: true }).click()
  await expect(field).toHaveValue(value)
})

test('maps Windows drive and current WSL distribution paths in the location field', async ({ page }) => {
  const response = await page.request.get('/api/v1/filesystem/locations', { headers: { Authorization: 'Bearer local-picker-test-session' } })
  const roots = await response.json()
  test.skip(roots.environment !== 'wsl', 'Windows paths are only meaningful on a WSL host')
  await page.getByRole('button', { name: 'Open project', exact: true }).click()
  await page.getByRole('button', { name: 'Browse: Project directory', exact: true }).click()
  const dialog = await fixtureFolder(page)
  const address = dialog.getByLabel('Location (optional: paste a path)', { exact: true })
  const original = await address.inputValue()
  await address.fill('C:\\')
  await dialog.getByRole('button', { name: 'Go', exact: true }).click()
  await expect(address).toHaveValue(/^\//)
  await expect(dialog.locator('[role="alert"]')).not.toBeVisible()
  const unc = `\\\\wsl.localhost\\${roots.distribution}${original.replaceAll('/', '\\')}`
  await address.fill(unc)
  await dialog.getByRole('button', { name: 'Go', exact: true }).click()
  await expect(address).toHaveValue(original)
  await dialog.getByRole('button', { name: 'Cancel', exact: true }).click()
})

test('supports the Chinese dialog and dark theme', async ({ page }, info) => {
  await page.getByRole('button', { name: 'Change language' }).click()
  await page.getByRole('button', { name: 'Toggle theme' }).click()
  await page.getByRole('button', { name: '新建工程', exact: true }).last().click()
  await page.getByRole('button', { name: '浏览: 工程文件夹', exact: true }).click()
  const dialog = await fixtureFolder(page)
  await expect(dialog.getByRole('heading', { name: '选择文件夹' })).toBeVisible()
  await expect(page.locator('body')).toHaveClass(/body--dark/)
  await page.screenshot({ path: info.outputPath('file-picker-zh.png'), animations: 'disabled' })
  await dialog.getByRole('button', { name: '取消', exact: true }).click()
  await expect(dialog).not.toBeVisible()
})

test('keeps the same dialog bounds for long names, empty folders and filtered lists', async ({ page }) => {
  await page.getByRole('button', { name: 'Open project', exact: true }).click()
  await page.getByRole('button', { name: 'Browse: Project directory', exact: true }).click()
  const dialog = await fixtureFolder(page)
  for (const viewport of [{width:1366,height:768},{width:911,height:512}]) {
    await page.setViewportSize(viewport)
    const original = (await dialog.boundingBox())!
    const stable = async () => {
      const bounds = (await dialog.boundingBox())!
      for (const key of ['x','y','width','height'] as const) expect(Math.abs(bounds[key]-original[key])).toBeLessThan(2)
      expect(bounds.y+bounds.height).toBeLessThanOrEqual(viewport.height)
      expect(await dialog.evaluate(el=>el.scrollHeight>el.clientHeight)).toBe(false)
      await expect(dialog.getByRole('button',{name:'Use selection',exact:true})).toBeVisible()
    }
    await dialog.locator('.picker-entries').getByText(/^Long folder name/).click()
    await expect(dialog.locator('.picker-entries .q-item')).toHaveCount(40)
    await stable()
    expect(await dialog.locator('.picker-entries').evaluate(el=>el.scrollHeight>el.clientHeight)).toBe(true)
    await dialog.getByLabel('Filter this folder',{exact:true}).fill('no-such-file')
    await expect(dialog.getByText('No matching items in this folder.',{exact:true})).toBeVisible()
    await stable()
    await dialog.getByRole('button',{name:'Parent folder',exact:true}).click()
    await dialog.locator('.picker-entries').getByText('目录 空格',{exact:true}).click()
    await expect(dialog.getByText('No matching items in this folder.',{exact:true})).toBeVisible()
    await stable()
    await dialog.getByRole('button',{name:'Parent folder',exact:true}).click()
    await expect(dialog.locator('.picker-entries').getByText('Picker fixtures',{exact:true})).toHaveCount(0)
  }
})
