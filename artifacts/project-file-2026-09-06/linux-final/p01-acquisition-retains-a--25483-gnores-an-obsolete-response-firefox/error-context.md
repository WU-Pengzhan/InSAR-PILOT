# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: p01-acquisition.spec.ts >> retains a basket across searches and ignores an obsolete response
- Location: e2e/p01-acquisition.spec.ts:18:1

# Error details

```
Test timeout of 30000ms exceeded while running "beforeEach" hook.
```

```
Error: locator.fill: Test timeout of 30000ms exceeded.
Call log:
  - waiting for getByLabel('West, south, east, north', { exact: true })

```

# Page snapshot

```yaml
- generic [ref=e3]:
  - banner [ref=e4]:
    - toolbar [ref=e5]:
      - generic [ref=e6] [cursor=pointer]:
        - img "InSAR-PILOT logo" [ref=e7]
        - generic [ref=e8]: InSAR-PILOT
        - generic [ref=e9]: NEXT
      - separator [ref=e10]
      - generic [ref=e11]: SAR / InSAR workbench
      - button "24 CPU" [ref=e12] [cursor=pointer]:
        - generic [aria-hidden] [ref=e13]: memory
      - button "Downloads" [ref=e15] [cursor=pointer]:
        - generic [ref=e16]:
          - img [aria-hidden] [ref=e17]: download
          - generic [ref=e18]: Downloads
      - button "Explore" [ref=e19] [cursor=pointer]:
        - generic [ref=e20]:
          - img [aria-hidden] [ref=e21]: travel_explore
          - generic [ref=e22]: Explore
      - button "Change language" [ref=e23] [cursor=pointer]:
        - img [aria-hidden] [ref=e25]: translate
      - button "Toggle theme" [ref=e26] [cursor=pointer]:
        - img [aria-hidden] [ref=e28]: dark_mode
      - generic [ref=e29]:
        - status [ref=e30]: Backend running
        - button "Exit app" [ref=e32] [cursor=pointer]:
          - generic [ref=e33]:
            - img [aria-hidden] [ref=e34]: power_settings_new
            - generic [ref=e35]: Exit app
  - main [ref=e37]:
    - generic [ref=e38]:
      - complementary [ref=e40]:
        - generic [ref=e41]:
          - generic [ref=e42]: PROJECT EXPLORER
          - button "Home" [ref=e43] [cursor=pointer]:
            - img [aria-hidden] [ref=e45]: home
        - generic [ref=e46]:
          - generic [aria-hidden] [ref=e47]: folder_open
          - paragraph [ref=e48]: Open a project to explore its data and processing history.
          - button "New project" [ref=e49] [cursor=pointer]
        - generic [ref=e52]:
          - button "Downloads" [ref=e53] [cursor=pointer]:
            - generic [ref=e54]:
              - img [aria-hidden] [ref=e55]: download
              - generic [ref=e56]: Downloads
          - button "Files view" [disabled] [ref=e57]:
            - generic [ref=e58]:
              - img [aria-hidden] [ref=e59]: folder
              - generic [ref=e60]: Files view
          - button "Data Library" [ref=e61] [cursor=pointer]:
            - generic [ref=e62]:
              - img [aria-hidden] [ref=e63]: inventory_2
              - generic [ref=e64]: Data Library
      - separator "Resize project explorer" [ref=e65]
      - generic [ref=e69]:
        - main [ref=e71]:
          - tablist "Workflow pages" [ref=e72]:
            - generic [ref=e73]:
              - tab "1 Search & download" [ref=e74] [cursor=pointer]
              - tab "2 Data & preparation" [disabled] [ref=e78]
              - tab "3 Parameters & generation" [disabled] [ref=e82]
              - tab "4 Run" [disabled] [ref=e86]
              - tab "5 Products & QC" [disabled] [ref=e90]
          - generic [ref=e95]:
            - generic [ref=e96]: YOUR SCIENCE, TRACEABLE
            - heading "From acquisitions to understanding." [level=1] [ref=e97]
            - paragraph [ref=e98]: One project. Every input, run and result connected.
            - generic [ref=e99]:
              - button "New project" [ref=e100] [cursor=pointer]:
                - generic [ref=e101]:
                  - img [aria-hidden] [ref=e102]: add
                  - generic [ref=e103]: New project
              - button "Open project" [ref=e104] [cursor=pointer]:
                - generic [ref=e105]:
                  - img [aria-hidden] [ref=e106]: folder_open
                  - generic [ref=e107]: Open project
              - button "Explore SAR data" [ref=e108] [cursor=pointer]:
                - generic [ref=e109]:
                  - img [aria-hidden] [ref=e110]: travel_explore
                  - generic [ref=e111]: Explore SAR data
            - generic [ref=e112]:
              - heading "Recent projects" [level=2] [ref=e113]
              - generic [ref=e114]: "3"
            - button "Picker existing /tmp/pilot-picker-e2e-g4n8edev/library/Picker fixtures/Existing Project/project.pilot 9/6/2026, 2:17:34 PM · Available" [ref=e115] [cursor=pointer]:
              - generic [aria-hidden] [ref=e116]: folder_open
              - generic [ref=e117]:
                - generic [ref=e118]: Picker existing
                - generic "/tmp/pilot-picker-e2e-g4n8edev/library/Picker fixtures/Existing Project/project.pilot" [ref=e119]
                - generic [ref=e120]: 9/6/2026, 2:17:34 PM · Available
              - status [ref=e121]: unassigned
              - generic [aria-hidden] [ref=e122]: chevron_right
            - button "新工程 windows-edge-1788675451863 /tmp/pilot-picker-e2e-g4n8edev/library/Picker fixtures/新工程 windows-edge-1788675451863/新工程 windows-edge-1788675451863.pilot 9/6/2026, 2:17:33 PM · Available" [ref=e123] [cursor=pointer]:
              - generic [aria-hidden] [ref=e124]: folder_open
              - generic [ref=e125]:
                - generic [ref=e126]: 新工程 windows-edge-1788675451863
                - generic "/tmp/pilot-picker-e2e-g4n8edev/library/Picker fixtures/新工程 windows-edge-1788675451863/新工程 windows-edge-1788675451863.pilot" [ref=e127]
                - generic [ref=e128]: 9/6/2026, 2:17:33 PM · Available
              - status [ref=e129]: unassigned
              - generic [aria-hidden] [ref=e130]: chevron_right
            - button "新工程 firefox-1788675442257 /tmp/pilot-picker-e2e-g4n8edev/library/Picker fixtures/新工程 firefox-1788675442257/新工程 firefox-1788675442257.pilot 9/6/2026, 2:17:23 PM · Available" [ref=e131] [cursor=pointer]:
              - generic [aria-hidden] [ref=e132]: folder_open
              - generic [ref=e133]:
                - generic [ref=e134]: 新工程 firefox-1788675442257
                - generic "/tmp/pilot-picker-e2e-g4n8edev/library/Picker fixtures/新工程 firefox-1788675442257/新工程 firefox-1788675442257.pilot" [ref=e135]
                - generic [ref=e136]: 9/6/2026, 2:17:23 PM · Available
              - status [ref=e137]: unassigned
              - generic [aria-hidden] [ref=e138]: chevron_right
        - separator "Resize" [ref=e139]
        - complementary [ref=e142]:
          - generic [ref=e143]:
            - generic [ref=e144]: INSPECTOR
            - button "Hide properties panel" [expanded] [ref=e145] [cursor=pointer]:
              - img [aria-hidden] [ref=e147]: chevron_right
          - heading "Object details" [level=3] [ref=e148]
          - tablist [ref=e149]:
            - generic [ref=e150]:
              - tab "Properties" [selected] [ref=e151] [cursor=pointer]
              - tab "QC" [ref=e155] [cursor=pointer]
              - tab "History" [ref=e159] [cursor=pointer]
          - generic [ref=e163]:
            - generic [aria-hidden] [ref=e164]: touch_app
            - paragraph [ref=e165]: Select a step, run or artifact to inspect its properties and provenance.
  - contentinfo [ref=e166]:
    - generic [ref=e167]:
      - generic [ref=e169]: Local engine
      - separator [ref=e170]
      - generic [ref=e171]: 0 processing jobs
      - button "Jobs" [ref=e172] [cursor=pointer]
      - button "Downloads" [ref=e175] [cursor=pointer]:
        - generic [ref=e176]:
          - img [aria-hidden] [ref=e177]: download
          - generic [ref=e178]: Downloads
      - generic [ref=e179]: Unassigned
```

# Test source

```ts
  1  | import {expect,test} from '@playwright/test'
  2  | 
  3  | const polygon={type:'Polygon',coordinates:[[[100,30],[102,30],[102,32],[100,32],[100,30]]]}
  4  | const product=(id:string)=>({product_key:id,provider_id:'asf-sentinel-1',remote_product_id:id,mission:'SENTINEL-1',platform:'SENTINEL-1D',acquisition_time:'2026-01-02T12:00:00Z',polarizations:['VV'],size_bytes:1024,footprint:polygon})
  5  | const group=(id:string)=>[{mission:'SENTINEL-1',error:null,page:{items:[product(id)],next_page:null}}]
  6  | 
  7  | test.beforeEach(async({page})=>{
  8  |  await page.addInitScript(()=>{localStorage.clear();sessionStorage.setItem('pilot-token','local-picker-test-session')})
  9  |  await page.route('**/api/v1/maps/imagery/**',route=>route.abort())
  10 |  await page.route('**/api/v1/data/search',route=>route.fulfill({json:group('S1D-first')}))
  11 |  await page.goto('/')
  12 |  await page.getByRole('button',{name:'Explore',exact:true}).click()
> 13 |  await page.getByLabel('West, south, east, north',{exact:true}).fill('100,30,102,32')
     |                                                                 ^ Error: locator.fill: Test timeout of 30000ms exceeded.
  14 |  await page.getByRole('button',{name:'Search SAR data',exact:true}).click()
  15 |  await expect(page.getByText('S1D-first',{exact:true})).toBeVisible()
  16 | })
  17 | 
  18 | test('retains a basket across searches and ignores an obsolete response',async({page})=>{
  19 |  const explorer=page.getByTestId('data-explorer')
  20 |  await explorer.getByRole('button',{name:'Select all loaded',exact:true}).click()
  21 |  let release:()=>void=()=>{}
  22 |  let calls=0
  23 |  await page.route('**/api/v1/data/search',async route=>{
  24 |   calls++
  25 |   if(calls===1){await new Promise<void>(resolve=>{release=resolve});await route.fulfill({json:group('obsolete')}).catch(()=>{});}
  26 |   else await route.fulfill({json:group('S1C-second')})
  27 |  })
  28 |  await explorer.getByRole('button',{name:'Search SAR data',exact:true}).click()
  29 |  await expect.poll(()=>calls).toBe(1)
  30 |  await explorer.getByLabel('Start date · UTC',{exact:true}).fill('2026-01-01')
  31 |  await explorer.getByRole('button',{name:'Search SAR data',exact:true}).click()
  32 |  await expect(explorer.getByText('S1C-second',{exact:true})).toBeVisible()
  33 |  release()
  34 |  await explorer.getByRole('button',{name:'Select all loaded',exact:true}).click()
  35 |  await explorer.getByRole('button',{name:'Selected scenes (2)',exact:true}).click()
  36 |  await expect(page.getByRole('dialog').getByText('S1D-first',{exact:true})).toBeVisible()
  37 |  await expect(page.getByRole('dialog').getByText('S1C-second',{exact:true})).toBeVisible()
  38 |  await page.keyboard.press('Escape')
  39 |  await expect(explorer.getByText('obsolete',{exact:true})).toHaveCount(0)
  40 | })
  41 | 
  42 | test('reviews all four EOF/DEM combinations and submits the frozen plan',async({page},info)=>{
  43 |  const requests:any[]=[]
  44 |  const commits:any[]=[]
  45 |  await page.route('**/api/v1/data/acquisition-preview',async route=>{
  46 |   const b=route.request().postDataJSON();requests.push(b)
  47 |   const roles=['SLC',...(b.include_orbits?['ORBIT']:[]),...(b.include_dem?['DEM']:[])]
  48 |   await route.fulfill({json:{plan_id:'review-'+requests.length,product_ids:b.product_ids,products:[product('S1D-first')],expected_revision:null,blockers:[],known_bytes:1024,unknown_files:roles.length-1,free_bytes:10*1024**3,destination:'/test/library',files:roles.map(role=>({file_id:role,role,scene_id:role==='DEM'?'COP30':'S1D-first',status:'planned'})),dem:b.include_dem?{geometry:polygon,tile_count:4,buffer_m:b.buffer_m}:null}})
  49 |  })
  50 |  await page.route('**/api/v1/data/acquisition-commit',async route=>{
  51 |   commits.push(route.request().postDataJSON())
  52 |   await route.fulfill({json:{project:null,job:{job_id:'new-attempt',status:'QUEUED'},plan_id:'review-4'}})
  53 |  })
  54 |  await page.getByRole('button',{name:'Select all loaded',exact:true}).click()
  55 |  await page.getByRole('button',{name:'Download only',exact:true}).click()
  56 |  const dialog=page.getByTestId('acquisition-dialog')
  57 |  for(const [orbits,dem] of [[false,false],[true,false],[false,true],[true,true]]){
  58 |   await dialog.getByRole('checkbox',{name:'Download precise EOF',exact:true}).setChecked(orbits!)
  59 |   await dialog.getByRole('checkbox',{name:'Download full-scene DEM',exact:true}).setChecked(dem!)
  60 |   await dialog.getByRole('button',{name:'Prepare review',exact:true}).click()
  61 |   await expect(dialog.getByRole('button',{name:'Start download',exact:true})).toBeEnabled()
  62 |   expect(requests.at(-1).include_orbits).toBe(orbits)
  63 |   expect(requests.at(-1).include_dem).toBe(dem)
  64 |   expect(requests.at(-1).buffer_m).toBe(20000)
  65 |  }
  66 |  await page.screenshot({path:info.outputPath('acquisition-review.png')})
  67 |  await dialog.getByRole('button',{name:'Start download',exact:true}).click()
  68 |  await expect(page.getByTestId('download-jobs')).toBeVisible()
  69 |  expect(commits).toHaveLength(1)
  70 |  expect(commits[0].plan_id).toBe('review-4')
  71 |  expect(commits[0].start_download).toBe(true)
  72 | })
  73 | 
  74 | test('uses keyboard controls and keeps imagery failure recoverable in Chinese dark mode',async({page},info)=>{
  75 |  await page.getByRole('button',{name:'Change language',exact:true}).click()
  76 |  await page.getByRole('button',{name:'Toggle theme',exact:true}).click()
  77 |  await page.getByRole('toolbar').getByRole('button',{name:'收起属性面板',exact:true}).click()
  78 |  const explorer=page.getByTestId('data-explorer')
  79 |  await expect(explorer.getByRole('button',{name:'重试底图',exact:true})).toBeVisible()
  80 |  await explorer.getByRole('button',{name:'框选 AOI',exact:true}).click()
  81 |  await explorer.locator('.leaflet-host').focus()
  82 |  await page.keyboard.press('Escape')
  83 |  await expect(explorer.getByRole('button',{name:'框选 AOI',exact:true})).toBeVisible()
  84 |  expect(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth)).toBe(false)
  85 |  await page.screenshot({path:info.outputPath('p01-zh-dark.png')})
  86 | })
  87 | 
```