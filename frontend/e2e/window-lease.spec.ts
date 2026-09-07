import {expect,test,chromium} from '@playwright/test'

test('one tab owns the service; another cannot take over and enters after close',async({page,context})=>{
  await page.goto('/')
  await expect(page.getByRole('heading',{name:'Recent projects',exact:true})).toBeVisible()
  await page.reload()
  await expect(page.getByRole('heading',{name:'Recent projects',exact:true})).toBeVisible({timeout:20000})
  const second=await context.newPage()
  await second.goto('/')
  await expect(second.getByTestId('window-gate')).toContainText('Workbench in use')
  await expect(second.getByRole('heading',{name:'Recent projects',exact:true})).toHaveCount(0)
  const rejected=await second.evaluate(async()=>{const r=await fetch('/api/v1/projects',{credentials:'same-origin'});return r.status})
  expect(rejected).toBe(423)
  await second.getByRole('button',{name:'Check again',exact:true}).click()
  await expect(second.getByTestId('window-gate')).toContainText('Workbench in use')
  await expect(page.getByRole('heading',{name:'Recent projects',exact:true})).toBeVisible()
  await page.close()
  await expect(second.getByRole('heading',{name:'Recent projects',exact:true})).toBeVisible({timeout:20000})
  await second.close()
})

test('an independent Chrome browser waits for Edge and connects after Edge closes',async({page,baseURL})=>{
  test.skip(process.platform!=='win32' || process.env.PILOT_TEST_CHROME!=='1','Installed Chrome check')
  await page.goto('/')
  await expect(page.getByRole('heading',{name:'Recent projects',exact:true})).toBeVisible()
  const chrome=await chromium.launch({channel:'chrome'})
  try{
    const other=await chrome.newPage()
    await other.goto(baseURL!)
    await expect(other.getByTestId('window-gate')).toContainText('Workbench in use')
    await page.close()
    await expect(other.getByRole('heading',{name:'Recent projects',exact:true})).toBeVisible({timeout:20000})
    const ws=other.waitForEvent('websocket')
    await other.getByRole('button',{name:/Picker existing/}).click()
    const stream=await ws
    const frame=await stream.waitForEvent('framereceived')
    expect(typeof frame.payload).toBe('string')
  }finally{await chrome.close()}
})


test('Chinese occupied screen stays out of the workbench and supports dark mode',async({page,context},info)=>{
  await page.goto('/')
  await expect(page.getByRole('heading',{name:'Recent projects',exact:true})).toBeVisible()
  const second=await context.newPage()
  await second.addInitScript(()=>{localStorage.setItem('pilot-language','zh');localStorage.setItem('pilot-dark','true')})
  await second.goto('/')
  await expect(second.getByTestId('window-gate')).toContainText('软件正在其他窗口使用')
  await expect(second.locator('.shell-splitter')).toHaveCount(0)
  await second.screenshot({path:info.outputPath('occupied-zh-dark.png')})
  await second.close()
})
