import { expect, test } from '@playwright/test'
const headers={Authorization:'Bearer local-picker-test-session'}
test.beforeEach(async({page})=>{
  await page.addInitScript(()=>{localStorage.clear();sessionStorage.setItem('pilot-token','local-picker-test-session')})
  await page.goto('/')
  await expect(page.getByRole('heading',{name:'Recent projects',exact:true})).toBeVisible()
})
test('shows invalid and incomplete states and imports a legacy project into a new directory',async({page},info)=>{
  const recent=await (await page.request.get('/api/v1/projects',{headers})).json()
  const parent=recent.find((p:any)=>p.name==='Picker existing').path.replace(/\/Existing Project$/,'')
  await page.getByRole('button',{name:'Open project',exact:true}).click()
  const field=page.getByLabel('Project file (.pilot)',{exact:true})
  await field.fill(parent+'/invalid.pilot')
  await expect(page.getByText('This file cannot be opened as a project',{exact:true})).toBeVisible()
  await expect(page.getByRole('button',{name:'Open',exact:true})).toBeDisabled()
  await field.fill(parent+'/Orphan Project/project.pilot')
  await expect(page.getByText('Incomplete project · companion database is missing',{exact:true})).toBeVisible()
  await field.fill(parent+'/Legacy Project/project.pilot')
  await expect(page.getByText('Desktop project · import into a new project',{exact:true})).toBeVisible()
  const name='Imported '+info.project.name+' '+Date.now()
  await page.getByLabel('Project name',{exact:true}).fill(name)
  await page.getByLabel('Save location',{exact:true}).fill(parent)
  await expect(page.getByText('Project file to create',{exact:true})).toBeVisible()
  await page.screenshot({path:info.outputPath('legacy-import.png')})
  await page.getByRole('button',{name:'Import as new project',exact:true}).click()
  await expect(page.locator('.project-name')).toHaveText(name)
  const legacy=await (await page.request.post('/api/v1/projects/inspect',{headers,data:{path:parent+'/Legacy Project/project.pilot'}})).json()
  expect(legacy.status).toBe('legacy')
})
test('discards delayed inspection after the user chooses another file',async({page})=>{
  let release!:()=>void
  const blocked=new Promise<void>(resolve=>{release=resolve})
  await page.route('**/projects/inspect',async route=>{
    if(route.request().postDataJSON().path==='first.pilot') {
      await blocked
      await route.fulfill({json:{status:'ready',message:'ready',project_file:'first.pilot',name:'Old response'}})
    } else await route.fulfill({json:{status:'invalid',message:'invalid',project_file:'second.pilot'}})
  })
  await page.getByRole('button',{name:'Open project',exact:true}).click()
  const field=page.getByLabel('Project file (.pilot)',{exact:true})
  const request=page.waitForRequest(r=>r.url().endsWith('/projects/inspect'))
  await field.fill('first.pilot');await request
  await field.fill('second.pilot')
  await expect(page.getByText('This file cannot be opened as a project',{exact:true})).toBeVisible()
  release()
  await expect(page.getByRole('button',{name:'Open',exact:true})).toBeDisabled()
  await expect(page.getByText('Old response',{exact:true})).toHaveCount(0)
})
