import {expect,test} from '@playwright/test'

const idle = {state:'RUNNING',shutdown_supported:true,can_exit:true,download_jobs:0,processing_jobs:0,worker_processes:0}

test('exit dialog preserves active jobs and points to task controls',async({page})=>{
  let shutdowns=0
  await page.route('**/api/v1/application/status',route=>route.fulfill({json:{...idle,can_exit:false,download_jobs:2,worker_processes:2}}))
  await page.route('**/api/v1/application/shutdown',route=>{shutdowns++;return route.fulfill({status:409,json:{detail:'Active tasks'}})})
  await page.goto('/#token=local-picker-test-session')
  await page.getByRole('button',{name:'Exit app',exact:true}).click()
  const dialog=page.getByTestId('exit-dialog')
  await expect(dialog).toContainText('2 download jobs')
  await expect(dialog.getByRole('button',{name:'Exit application',exact:true})).toHaveCount(0)
  await dialog.getByRole('button',{name:'View tasks',exact:true}).click()
  await expect(page.getByTestId('download-jobs')).toBeVisible()
  expect(shutdowns).toBe(0)
})

test('an acknowledged idle shutdown ends with a clear exit screen',async({page},info)=>{
  let exited=false
  await page.route('**/api/v1/application/status',route=>exited?route.abort('connectionrefused'):route.fulfill({json:idle}))
  await page.route('**/api/v1/application/shutdown',async route=>{await route.fulfill({status:202,json:{...idle,state:'STOPPING'}});exited=true})
  await page.goto('/#token=local-picker-test-session')
  await page.getByRole('button',{name:'Exit app',exact:true}).click()
  await page.getByTestId('exit-dialog').getByRole('button',{name:'Exit application',exact:true}).click()
  await expect(page.getByRole('heading',{name:'Exit complete',exact:true})).toBeVisible()
  await expect(page.getByTestId('application-exit-screen')).toContainText('insar-pilot-web --status')
  await expect(page.locator('.shell-splitter')).toHaveCount(0)
  await page.screenshot({path:info.outputPath('exit-complete.png')})
})

test('an unexpected disconnection is not reported as a successful exit',async({page})=>{
  let disconnected=false
  await page.route('**/api/v1/application/status',route=>disconnected?route.abort('connectionrefused'):route.fulfill({json:idle}))
  await page.goto('/#token=local-picker-test-session')
  await expect(page.getByRole('button',{name:'Exit app',exact:true})).toBeEnabled()
  disconnected=true
  await expect(page.getByRole('heading',{name:'Backend connection lost',exact:true})).toBeVisible()
  await expect(page.getByRole('heading',{name:'Exit complete',exact:true})).toHaveCount(0)
})
