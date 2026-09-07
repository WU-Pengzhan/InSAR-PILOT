import { expect, test } from '@playwright/test'

test('a fresh browser shows connection instructions without a raw API error', async ({ page }) => {
  await page.goto('/')
  await expect(page.getByTestId('session-required')).toBeVisible()
  await expect(page.getByText('Local session required.', { exact: true })).not.toBeVisible()
  await expect(page.getByTestId('session-required')).toContainText('insar-pilot-web')
})

test('a launcher link authenticates and later tabs reuse its cookie for API and WebSocket', async ({ page, context }) => {
  await page.goto('/#token=local-picker-test-session')
  await expect(page.getByRole('heading', { name: 'Recent projects' })).toBeVisible()
  expect(page.url()).not.toContain('#token=')
  const second = await context.newPage()
  await second.goto('/')
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
