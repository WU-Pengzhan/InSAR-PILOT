import {expect,test} from '@playwright/test'

const polygon={type:'Polygon',coordinates:[[[100,30],[102,30],[102,32],[100,32],[100,30]]]}
const product=(id:string)=>({product_key:id,provider_id:'asf-sentinel-1',remote_product_id:id,mission:'SENTINEL-1',platform:'SENTINEL-1D',acquisition_time:'2026-01-02T12:00:00Z',polarizations:['VV'],size_bytes:1024,footprint:polygon})
const group=(id:string)=>[{mission:'SENTINEL-1',error:null,page:{items:[product(id)],next_page:null}}]

test.beforeEach(async({page})=>{
 await page.addInitScript(()=>{localStorage.clear();sessionStorage.setItem('pilot-token','local-picker-test-session')})
 await page.route('**/api/v1/maps/imagery/**',route=>route.abort())
 await page.route('**/api/v1/data/search',route=>route.fulfill({json:group('S1D-first')}))
 await page.goto('/')
 await expect(page.getByRole('heading',{name:'Recent projects',exact:true})).toBeVisible()
 await expect(page.locator('.global-progress')).not.toBeVisible()
 await page.getByRole('button',{name:'Explore',exact:true}).click()
 await page.getByLabel('West, south, east, north',{exact:true}).fill('100,30,102,32')
 await page.getByRole('button',{name:'Search SAR data',exact:true}).click()
 await expect(page.getByText('S1D-first',{exact:true})).toBeVisible()
})

test('retains a basket across searches and ignores an obsolete response',async({page})=>{
 const explorer=page.getByTestId('data-explorer')
 await explorer.getByRole('button',{name:'Select all loaded',exact:true}).click()
 let release:()=>void=()=>{}
 let calls=0
 await page.route('**/api/v1/data/search',async route=>{
  calls++
  if(calls===1){await new Promise<void>(resolve=>{release=resolve});await route.fulfill({json:group('obsolete')}).catch(()=>{});}
  else await route.fulfill({json:group('S1C-second')})
 })
 await explorer.getByRole('button',{name:'Search SAR data',exact:true}).click()
 await expect.poll(()=>calls).toBe(1)
 await explorer.getByLabel('Start date · UTC',{exact:true}).fill('2026-01-01')
 await explorer.getByRole('button',{name:'Search SAR data',exact:true}).click()
 await expect(explorer.getByText('S1C-second',{exact:true})).toBeVisible()
 release()
 await explorer.getByRole('button',{name:'Select all loaded',exact:true}).click()
 await explorer.getByRole('button',{name:'Selected scenes (2)',exact:true}).click()
 await expect(page.getByRole('dialog').getByText('S1D-first',{exact:true})).toBeVisible()
 await expect(page.getByRole('dialog').getByText('S1C-second',{exact:true})).toBeVisible()
 await page.keyboard.press('Escape')
 await expect(explorer.getByText('obsolete',{exact:true})).toHaveCount(0)
})

test('reviews all four EOF/DEM combinations and submits the frozen plan',async({page},info)=>{
 const requests:any[]=[]
 const commits:any[]=[]
 await page.route('**/api/v1/data/acquisition-preview',async route=>{
  const b=route.request().postDataJSON();requests.push(b)
  const roles=['SLC',...(b.include_orbits?['ORBIT']:[]),...(b.include_dem?['DEM']:[])]
  await route.fulfill({json:{plan_id:'review-'+requests.length,product_ids:b.product_ids,products:[product('S1D-first')],expected_revision:null,blockers:[],known_bytes:1024,unknown_files:roles.length-1,free_bytes:10*1024**3,destination:'/test/library',files:roles.map(role=>({file_id:role,role,scene_id:role==='DEM'?'COP30':'S1D-first',status:'planned'})),dem:b.include_dem?{geometry:polygon,tile_count:4,buffer_m:b.buffer_m}:null}})
 })
 await page.route('**/api/v1/data/acquisition-commit',async route=>{
  commits.push(route.request().postDataJSON())
  await route.fulfill({json:{project:null,job:{job_id:'new-attempt',status:'QUEUED'},plan_id:'review-4'}})
 })
 await page.getByRole('button',{name:'Select all loaded',exact:true}).click()
 await page.getByRole('button',{name:'Download only',exact:true}).click()
 const dialog=page.getByTestId('acquisition-dialog')
 for(const [orbits,dem] of [[false,false],[true,false],[false,true],[true,true]]){
  await dialog.getByRole('checkbox',{name:'Download precise EOF',exact:true}).setChecked(orbits!)
  await dialog.getByRole('checkbox',{name:'Download full-scene DEM',exact:true}).setChecked(dem!)
  await dialog.getByRole('button',{name:'Prepare review',exact:true}).click()
  await expect(dialog.getByRole('button',{name:'Start download',exact:true})).toBeEnabled()
  expect(requests.at(-1).include_orbits).toBe(orbits)
  expect(requests.at(-1).include_dem).toBe(dem)
  expect(requests.at(-1).buffer_m).toBe(20000)
 }
 await page.screenshot({path:info.outputPath('acquisition-review.png')})
 await dialog.getByRole('button',{name:'Start download',exact:true}).click()
 await expect(page.getByTestId('download-jobs')).toBeVisible()
 expect(commits).toHaveLength(1)
 expect(commits[0].plan_id).toBe('review-4')
 expect(commits[0].start_download).toBe(true)
})

test('uses keyboard controls and keeps imagery failure recoverable in Chinese dark mode',async({page},info)=>{
 await page.getByRole('button',{name:'Change language',exact:true}).click()
 await page.getByRole('button',{name:'Toggle theme',exact:true}).click()
 await expect(page.locator('.inspector')).not.toBeVisible()
 const explorer=page.getByTestId('data-explorer')
 await expect(explorer.getByRole('button',{name:'重试底图',exact:true})).toBeVisible()
 await explorer.getByRole('button',{name:'框选 AOI',exact:true}).click()
 await explorer.locator('.leaflet-host').focus()
 await page.keyboard.press('Escape')
 await expect(explorer.getByRole('button',{name:'框选 AOI',exact:true})).toBeVisible()
 expect(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth)).toBe(false)
 await page.screenshot({path:info.outputPath('p01-zh-dark.png')})
})
