import { expect, test } from '@playwright/test'

test('reports actual runtime states, clears edited results and recovers from errors',async({page},info)=>{
  await page.addInitScript(()=>{sessionStorage.setItem('pilot-token','local-picker-test-session');localStorage.setItem('pilot-language','zh');localStorage.setItem('pilot-dark','true')})
  await page.route('**/api/v1/compute/profiles',route=>route.fulfill({json:[]}))
  let fail=false
  await page.route('**/api/v1/compute/check',route=>{
    const body=route.request().postDataJSON()
    if(fail)return route.fulfill({status:503,json:{detail:'Check service unavailable'}})
    return route.fulfill({json:{processor:body.processor,python_executable:body.python_executable||'/fixture/python',status:body.processor==='isce2'?'READY':'UNAVAILABLE',reason:'requirements_missing',checked_at:'2026-09-07T12:00:00Z',checks:[{name:body.processor==='isce2'?'ISCE2':'ISCE3',ok:body.processor==='isce2',detail:body.processor==='isce2'?'2.6.5':'missing_module:isce3'}]}})
  })
  await page.goto('/')
  await page.getByTestId('compute-entry').click()
  const s1=page.getByTestId('isce2-runtime'),nisar=page.getByTestId('isce3-runtime')
  await expect(s1.getByRole('status')).toHaveText('环境就绪')
  await expect(nisar.getByRole('status')).toHaveText('当前不可运行')
  await expect(nisar).toContainText('缺少模块：isce3')
  await expect(page.getByText('CPU adapters available.')).toHaveCount(0)
  await s1.getByRole('textbox').fill('/a/very/long/user/managed/path/python')
  await expect(s1.getByRole('status')).toHaveText('尚未确认')
  fail=true
  await s1.getByRole('button',{name:'重新检测',exact:true}).click()
  await expect(s1.getByRole('alert')).toContainText('Check service unavailable')
  fail=false
  await s1.getByRole('button',{name:'重新检测',exact:true}).click()
  await expect(s1.getByRole('status')).toHaveText('环境就绪')
  await expect(s1).toContainText('/a/very/long/user/managed/path/python')
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBeTruthy()
  await page.screenshot({path:info.outputPath('runtime-zh-dark.png')})
})

test('shows the unavailable environment in English light mode at 1440px',async({page},info)=>{
  await page.setViewportSize({width:1440,height:900})
  await page.addInitScript(()=>{sessionStorage.setItem('pilot-token','local-picker-test-session');localStorage.setItem('pilot-language','en');localStorage.setItem('pilot-dark','false')})
  await page.route('**/api/v1/compute/profiles',route=>route.fulfill({json:[]}))
  await page.route('**/api/v1/compute/check',route=>route.fulfill({json:{python_executable:'/missing/python',status:'UNAVAILABLE',reason:'python_unavailable',checked_at:'2026-09-07T12:00:00Z',checks:[]}}))
  await page.goto('/')
  await page.getByTestId('compute-entry').click()
  await expect(page.getByRole('heading',{name:'Processing environment',exact:true})).toBeVisible()
  await expect(page.getByTestId('isce2-runtime').getByRole('alert')).toHaveText('Python is missing or not executable.')
  await expect(page.getByTestId('isce3-runtime').getByRole('status')).toHaveText('Cannot run')
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBeTruthy()
  await page.screenshot({path:info.outputPath('runtime-en-light.png')})
})
