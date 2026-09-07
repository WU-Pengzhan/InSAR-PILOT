import {expect,test,chromium,firefox} from '@playwright/test'
import {mkdtemp,rm} from 'node:fs/promises'
import {tmpdir} from 'node:os'
import {join,dirname} from 'node:path'

test('reopens the same browser profile after the browser process exits',async({browserName,baseURL})=>{
  const type=browserName==='firefox'?firefox:chromium
  const options={baseURL,...(process.platform==='win32'?{channel:'msedge'}:{})}
  const temporaryRoot=tmpdir()
  const profile=await mkdtemp(join(temporaryRoot,'pilot-reconnect-'))
  try{
  const first=await type.launchPersistentContext(profile,options)
  try{
    const page=await first.newPage()
    await page.goto('/#token=local-picker-test-session')
    await expect(page.getByRole('heading',{name:'Recent projects',exact:true})).toBeVisible()
    expect((await first.cookies()).some(c=>c.name==='pilot_session' && c.expires>Date.now()/1000)).toBeTruthy()
  }finally{await first.close()}
  const second=await type.launchPersistentContext(profile,options)
  try{
    const page=await second.newPage()
    await page.goto('/')
    await expect(page.getByRole('heading',{name:'Recent projects',exact:true})).toBeVisible()
    expect(await page.evaluate(()=>sessionStorage.getItem('pilot-token'))).toBeNull()
    await expect(page.getByTestId('session-required')).toHaveCount(0)
  }finally{await second.close()}
  }finally{
    if(dirname(profile)!==temporaryRoot)throw Error('Unexpected test profile location')
    await rm(profile,{recursive:true,force:true})
  }
})

test('an independent context waits until the current owner closes',async({page,browser,baseURL})=>{
  await page.goto('/')
  await expect(page.getByRole('heading',{name:'Recent projects',exact:true})).toBeVisible()
  const context=await browser.newContext({baseURL})
  try{
    const other=await context.newPage()
    await other.goto('/')
    await expect(other.getByTestId('window-gate')).toContainText('Workbench in use')
    await page.close()
    await expect(other.getByRole('heading',{name:'Recent projects',exact:true})).toBeVisible()
    expect(await other.evaluate(()=>sessionStorage.getItem('pilot-token'))).toBeNull()
    await context.clearCookies()
    await other.reload()
    await expect(other.getByRole('heading',{name:'Recent projects',exact:true})).toBeVisible()
  }finally{await context.close()}
})
