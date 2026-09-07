import { chromium, expect, test } from '@playwright/test'

test('a fresh browser opens the local address without launcher credentials', async ({ page }) => {
  await page.goto('/')
  await expect(page.getByRole('heading', { name: 'Recent projects' })).toBeVisible()
  await expect(page.getByTestId('session-required')).toHaveCount(0)
  expect(await page.evaluate(() => sessionStorage.getItem('pilot-token'))).toBeNull()

})

test('a later tab waits despite a shared cookie then uses API and WebSocket after release', async ({ page, context }) => {
  await page.goto('/#token=local-picker-test-session')
  await expect(page.getByRole('heading', { name: 'Recent projects' })).toBeVisible()
  expect(page.url()).not.toContain('#token=')
  const second = await context.newPage()
  await second.goto('/')
  await expect(second.getByTestId('window-gate')).toContainText('Workbench in use')
  await page.close()
  await expect(second.getByRole('heading', { name: 'Recent projects' })).toBeVisible()
  expect(await second.evaluate(() => sessionStorage.getItem('pilot-token'))).toBeNull()
  const socket = second.waitForEvent('websocket')
  await second.getByRole('button', { name: /Picker existing/ }).click()
  const ws = await socket
  const message = await ws.waitForEvent('framereceived')
  expect(typeof message.payload).toBe('string')
  await expect(second.getByTestId('session-required')).not.toBeVisible()
  await second.close()
})

test('a stale tab token does not override a valid cookie', async ({ page }) => {
  await page.goto('/#token=local-picker-test-session')
  await expect(page.getByRole('heading', { name: 'Recent projects' })).toBeVisible()
  await page.evaluate(() => sessionStorage.setItem('pilot-token', 'expired-fixture'))
  await page.reload()
  await expect(page.getByRole('heading', { name: 'Recent projects' })).toBeVisible()
  await expect(page.getByTestId('session-required')).not.toBeVisible()
  expect(await page.evaluate(() => sessionStorage.getItem('pilot-token'))).toBeNull()
})


test('Chrome independently opens the localhost address without a launcher token',async({baseURL})=>{
  test.skip(process.platform!=='win32' || process.env.PILOT_TEST_CHROME!=='1','Optional installed Windows Chrome check')
  const chrome=await chromium.launch({channel:'chrome'})
  try{
    const context=await chrome.newContext()
    const page=await context.newPage()
    await page.goto(baseURL!.replace('127.0.0.1','localhost'))
    await expect(page.getByRole('heading',{name:'Recent projects',exact:true})).toBeVisible()
    expect(await page.evaluate(()=>sessionStorage.getItem('pilot-token'))).toBeNull()
    const socket=page.waitForEvent('websocket')
    await page.getByRole('button',{name:/Picker existing/}).click()
    const ws=await socket
    const frame=await ws.waitForEvent('framereceived')
    expect(typeof frame.payload).toBe('string')
    await expect(page.getByTestId('session-required')).toHaveCount(0)
  }finally{await chrome.close()}
})
