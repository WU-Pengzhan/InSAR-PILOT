# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: shell-layout.spec.ts >> keeps five fixed pages across auxiliary views and project selection
- Location: e2e/shell-layout.spec.ts:15:1

# Error details

```
Test timeout of 30000ms exceeded.
```

```
Error: locator.click: Test timeout of 30000ms exceeded.
Call log:
  - waiting for getByTestId('primary-pages').getByRole('tab', { name: '3 Parameters & generation', exact: true })
    - locator resolved to <div role="tab" tabindex="-1" aria-disabled="true" aria-selected="false" class="q-tab relative-position self-stretch flex flex-center text-center q-tab--inactive q-tab--no-caps disabled">…</div>
  - attempting click action
    2 × waiting for element to be visible, enabled and stable
      - element is not enabled
    - retrying click action
    - waiting 20ms
    2 × waiting for element to be visible, enabled and stable
      - element is not enabled
    - retrying click action
      - waiting 100ms
    55 × waiting for element to be visible, enabled and stable
       - element is not enabled
     - retrying click action
       - waiting 500ms

```

# Page snapshot

```yaml
- generic [ref=e3]:
  - banner [ref=e4]:
    - toolbar [ref=e5]:
      - generic [ref=e6] [cursor=pointer]:
        - img "InSAR-PILOT logo" [ref=e7]
        - generic [ref=e8]: InSAR-PILOT
      - separator [ref=e9]
      - generic [ref=e10]: No project open
      - button "24 CPU" [ref=e11] [cursor=pointer]:
        - generic [aria-hidden] [ref=e12]: memory
      - button "Downloads" [ref=e14] [cursor=pointer]:
        - generic [ref=e15]:
          - img [aria-hidden] [ref=e16]: download
          - generic [ref=e17]: Downloads
      - button "Explore" [ref=e18] [cursor=pointer]:
        - generic [ref=e19]:
          - img [aria-hidden] [ref=e20]: travel_explore
          - generic [ref=e21]: Explore
      - button "Change language" [ref=e22] [cursor=pointer]:
        - img [aria-hidden] [ref=e24]: translate
      - button "Toggle theme" [ref=e25] [cursor=pointer]:
        - img [aria-hidden] [ref=e27]: dark_mode
      - generic [ref=e28]:
        - status [ref=e29]: Backend running
        - button "Exit app" [ref=e31] [cursor=pointer]:
          - generic [ref=e32]:
            - img [aria-hidden] [ref=e33]: power_settings_new
            - generic [ref=e34]: Exit app
  - main [ref=e36]:
    - progressbar [ref=e37]
    - generic [ref=e40]:
      - complementary [ref=e42]:
        - generic [ref=e43]:
          - generic [ref=e44]: PROJECT EXPLORER
          - button "Home" [ref=e45] [cursor=pointer]:
            - img [aria-hidden] [ref=e47]: home
        - generic [ref=e48]:
          - generic [aria-hidden] [ref=e49]: folder_open
          - paragraph [ref=e50]: Open a project to explore its data and processing history.
          - button "New project" [ref=e51] [cursor=pointer]
        - generic [ref=e54]:
          - button "Downloads" [ref=e55] [cursor=pointer]:
            - generic [ref=e56]:
              - img [aria-hidden] [ref=e57]: download
              - generic [ref=e58]: Downloads
          - button "Files view" [disabled] [ref=e59]:
            - generic [ref=e60]:
              - img [aria-hidden] [ref=e61]: folder
              - generic [ref=e62]: Files view
          - button "Data Library" [ref=e63] [cursor=pointer]:
            - generic [ref=e64]:
              - img [aria-hidden] [ref=e65]: inventory_2
              - generic [ref=e66]: Data Library
      - separator "Resize project explorer" [ref=e67]
      - main [ref=e73]:
        - tablist "Workflow pages" [ref=e74]:
          - generic [ref=e75]:
            - tab "1 Search & download" [ref=e76] [cursor=pointer]
            - tab "2 Data & preparation" [disabled] [ref=e80]
            - tab "3 Parameters & generation" [disabled] [ref=e84]
            - tab "4 Run" [disabled] [ref=e88]
            - tab "5 Products & QC" [disabled] [ref=e92]
        - generic [ref=e97]:
          - generic [ref=e98]: SAR / InSAR WORKBENCH
          - heading "Choose your project" [level=1] [ref=e99]
          - paragraph [ref=e100]: Open an existing project, create a new one, or start with a data search.
          - generic [ref=e101]:
            - button "New project" [ref=e102] [cursor=pointer]:
              - generic [ref=e103]:
                - img [aria-hidden] [ref=e104]: add
                - generic [ref=e105]: New project
            - button "Open project" [ref=e106] [cursor=pointer]:
              - generic [ref=e107]:
                - img [aria-hidden] [ref=e108]: folder_open
                - generic [ref=e109]: Open project
            - button "Explore SAR data" [ref=e110] [cursor=pointer]:
              - generic [ref=e111]:
                - img [aria-hidden] [ref=e112]: travel_explore
                - generic [ref=e113]: Explore SAR data
          - generic [ref=e114]:
            - heading "Recent projects" [level=2] [ref=e115]
            - generic [ref=e116]: "3"
          - button "Picker existing /tmp/pilot-picker-e2e-x1sks7ta/library/Picker fixtures/Existing Project/project.pilot 9/7/2026, 9:51:56 AM · No data selected · 0 running / queued" [ref=e117] [cursor=pointer]:
            - generic [aria-hidden] [ref=e118]: folder_open
            - generic [ref=e119]:
              - generic [ref=e120]: Picker existing
              - generic "/tmp/pilot-picker-e2e-x1sks7ta/library/Picker fixtures/Existing Project/project.pilot" [ref=e121]
              - generic [ref=e122]: 9/7/2026, 9:51:56 AM · No data selected · 0 running / queued
            - status [ref=e123]: unassigned
            - generic [aria-hidden] [ref=e124]: chevron_right
          - button "Layout firefox 1788745912932 /tmp/pilot-picker-e2e-x1sks7ta/library/Picker fixtures/Layout firefox 1788745912932/Layout firefox 1788745912932.pilot 9/7/2026, 9:51:54 AM · No data selected · 0 running / queued" [ref=e125] [cursor=pointer]:
            - generic [aria-hidden] [ref=e126]: folder_open
            - generic [ref=e127]:
              - generic [ref=e128]: Layout firefox 1788745912932
              - generic "/tmp/pilot-picker-e2e-x1sks7ta/library/Picker fixtures/Layout firefox 1788745912932/Layout firefox 1788745912932.pilot" [ref=e129]
              - generic [ref=e130]: 9/7/2026, 9:51:54 AM · No data selected · 0 running / queued
            - status [ref=e131]: unassigned
            - generic [aria-hidden] [ref=e132]: chevron_right
          - button "Imported firefox 1788745908368 /tmp/pilot-picker-e2e-x1sks7ta/library/Picker fixtures/Imported firefox 1788745908368/Imported firefox 1788745908368.pilot 9/7/2026, 9:51:48 AM · No data selected · 0 running / queued" [ref=e133] [cursor=pointer]:
            - generic [aria-hidden] [ref=e134]: folder_open
            - generic [ref=e135]:
              - generic [ref=e136]: Imported firefox 1788745908368
              - generic "/tmp/pilot-picker-e2e-x1sks7ta/library/Picker fixtures/Imported firefox 1788745908368/Imported firefox 1788745908368.pilot" [ref=e137]
              - generic [ref=e138]: 9/7/2026, 9:51:48 AM · No data selected · 0 running / queued
            - status [ref=e139]: unassigned
            - generic [aria-hidden] [ref=e140]: chevron_right
  - contentinfo [ref=e141]:
    - generic [ref=e142]:
      - generic [ref=e144]: Working…
      - separator [ref=e145]
      - generic [ref=e146]: 0 processing jobs
      - button "Jobs" [ref=e147] [cursor=pointer]
      - button "Downloads" [ref=e150] [cursor=pointer]:
        - generic [ref=e151]:
          - img [aria-hidden] [ref=e152]: download
          - generic [ref=e153]: Downloads
      - generic [ref=e154]: Unassigned
```

# Test source

```ts
  1   | import { expect, test } from '@playwright/test'
  2   | 
  3   | const png = Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=', 'base64')
  4   | test.beforeEach(async ({page}) => {
  5   |   await page.addInitScript(() => {
  6   |     if (!sessionStorage.getItem('shell-init')) {localStorage.clear();sessionStorage.setItem('shell-init','1')}
  7   |     sessionStorage.setItem('pilot-token','local-picker-test-session')
  8   |   })
  9   |   await page.route('**/api/v1/maps/imagery/**', route => route.fulfill({contentType:'image/png',body:png}))
  10  |   await page.route('**/api/v1/data/download-readiness', route => route.fulfill({json:{aria2_available:true,credentials_configured:true,gdal_available:true,library_path:'/fixture/library',aria2_executable:'/usr/bin/aria2c'}}))
  11  |   await page.goto('/')
  12  |   await expect(page.getByRole('heading',{name:'Recent projects',exact:true})).toBeVisible()
  13  | })
  14  | 
  15  | test('keeps five fixed pages across auxiliary views and project selection', async ({page}) => {
  16  |   const primary=page.getByTestId('primary-pages')
  17  |   await expect(primary.getByRole('tab')).toHaveCount(5)
  18  |   await expect(primary.getByRole('tab',{name:'2 Data & preparation'})).toBeDisabled()
  19  |   for (let i=0;i<2;i++) {
  20  |     await page.getByRole('toolbar').getByRole('button',{name:'Explore',exact:true}).click()
  21  |     await page.getByRole('toolbar').getByRole('button',{name:'Downloads',exact:true}).click()
  22  |     await page.getByRole('button',{name:'Home',exact:true}).click()
  23  |   }
  24  |   let release!:()=>void
  25  |   const pending=new Promise<void>(resolve=>{release=resolve})
  26  |   await page.route('**/api/v1/projects/*/artifacts',async route=>{await pending;await route.fulfill({json:[]})})
  27  |   await page.locator('.project-card').filter({hasText:'Picker existing'}).click()
> 28  |   await primary.getByRole('tab',{name:'3 Parameters & generation',exact:true}).click()
      |                                                                                ^ Error: locator.click: Test timeout of 30000ms exceeded.
  29  |   release()
  30  |   await expect(page.locator('.global-progress')).not.toBeVisible()
  31  |   await expect(primary.getByRole('tab',{name:'3 Parameters & generation',exact:true})).toHaveAttribute('aria-selected','true')
  32  |   for (const name of ['3 Parameters & generation','4 Run','5 Products & QC','2 Data & preparation']) {
  33  |     await primary.getByRole('tab',{name,exact:true}).click()
  34  |     await expect(primary.getByRole('tab',{name,exact:true})).toHaveAttribute('aria-selected','true')
  35  |   }
  36  |   await expect(primary.getByRole('tab')).toHaveCount(5)
  37  |   await page.getByRole('button',{name:'Home',exact:true}).click()
  38  |   await expect(primary.getByRole('tab')).toHaveCount(5)
  39  | })
  40  | 
  41  | test('resizes the project explorer, preserves width and scrolls full names', async ({page},info) => {
  42  |   const longName='S1D_IW_SLC__'+ 'long_acquisition_name_'.repeat(14)
  43  |   await page.route('**/api/v1/projects/*/artifacts', route=>route.fulfill({json:[{artifact_id:'long-source',created_by_run:null,type:'Sentinel1SLC',metadata:{native_product_id:longName},assets:[],mission:'sentinel1_tops'}]}))
  44  |   await page.locator('.project-card').filter({hasText:'Picker existing'}).click()
  45  |   const tree=page.locator('.project-tree-scroll')
  46  |   await expect(tree.getByText(longName,{exact:true})).toBeVisible()
  47  |   expect(await tree.evaluate(el=>el.scrollWidth>el.clientWidth)).toBe(true)
  48  |   await tree.evaluate(el=>{el.scrollLeft=300})
  49  |   expect(await tree.evaluate(el=>el.scrollLeft)).toBeGreaterThan(200)
  50  |   const separator=page.getByRole('separator',{name:'Resize project explorer'})
  51  |   const before=(await page.locator('.explorer').boundingBox())!.width
  52  |   const b=(await separator.boundingBox())!
  53  |   await page.mouse.move(b.x+b.width/2,b.y+100);await page.mouse.down()
  54  |   await page.mouse.move(b.x+80,b.y+100,{steps:12});await page.mouse.up()
  55  |   await expect.poll(async()=> (await page.locator('.explorer').boundingBox())!.width).toBeGreaterThan(before+50)
  56  |   const width=(await page.locator('.explorer').boundingBox())!.width
  57  |   await expect.poll(async()=>Math.abs(Number(await page.evaluate(()=>localStorage.getItem('pilot-explorer-width')))-width)).toBeLessThan(3)
  58  |   await page.reload()
  59  |   await expect.poll(async()=> Math.abs((await page.locator('.explorer').boundingBox())!.width-width)).toBeLessThan(3)
  60  |   await separator.focus();await page.keyboard.press('ArrowLeft')
  61  |   await expect.poll(async()=> (await page.locator('.explorer').boundingBox())!.width).toBeLessThan(width-5)
  62  |   await page.screenshot({path:info.outputPath('explorer-width.png')})
  63  | })
  64  | 
  65  | test('gives the map more width and keeps environment details collapsed', async ({page},info) => {
  66  |   await page.getByRole('toolbar').getByRole('button',{name:'Explore',exact:true}).click()
  67  |   const summary=page.locator('.readiness-summary')
  68  |   await expect(summary).toHaveAttribute('aria-expanded','false')
  69  |   await expect(summary).toContainText('Download environment configured')
  70  |   const controls=(await page.locator('.acquisition-controls').boundingBox())!
  71  |   const map=(await page.getByTestId('search-map').first().boundingBox())!
  72  |   expect(controls.width).toBeLessThanOrEqual(341)
  73  |   expect(map.width).toBeGreaterThan(controls.width)
  74  |   await expect(page.getByRole('button',{name:/Hide filters|Show filters/})).toHaveCount(0)
  75  |   await expect(page.getByRole('toolbar').getByRole('button',{name:/properties panel/})).toHaveCount(0)
  76  |   await page.getByRole('button',{name:'Hide properties panel',exact:true}).click()
  77  |   const reopen=page.locator('.inspector-rail').getByRole('button',{name:'Show properties panel',exact:true})
  78  |   await expect(reopen).toBeFocused()
  79  |   await expect(reopen).toHaveAttribute('aria-expanded','false')
  80  |   const rail=(await page.locator('.inspector-rail').boundingBox())!
  81  |   expect(rail.x+rail.width).toBeCloseTo(1366,0)
  82  |   await expect.poll(async()=> (await page.getByTestId('search-map').boundingBox())!.width).toBeGreaterThan(map.width+100)
  83  |   expect((await page.getByTestId('search-map').boundingBox())!.height).toBeCloseTo(map.height,0)
  84  |   await page.keyboard.press('Enter')
  85  |   await expect(page.getByRole('button',{name:'Hide properties panel',exact:true})).toBeFocused()
  86  |   await expect(page.locator('.inspector')).toBeVisible()
  87  |   await summary.click()
  88  |   await expect(page.getByText('/fixture/library',{exact:true})).toBeVisible()
  89  |   await summary.click()
  90  |   await expect(page.getByText('/fixture/library',{exact:true})).not.toBeVisible()
  91  |   await page.locator('.workspace-content').evaluate(el=>{el.scrollTop=0})
  92  |   await page.screenshot({path:info.outputPath('layout-en.png')})
  93  |   await page.getByRole('button',{name:'Change language',exact:true}).click()
  94  |   await page.getByRole('button',{name:'Toggle theme',exact:true}).click()
  95  |   await expect(page.getByTestId('primary-pages').getByRole('tab')).toHaveCount(5)
  96  |   await page.screenshot({path:info.outputPath('layout-zh-dark.png')})
  97  |   await page.getByRole('button',{name:'收起属性面板',exact:true}).first().click()
  98  |   await page.setViewportSize({width:1920,height:768})
  99  |   await expect.poll(async()=> (await page.getByTestId('search-map').boundingBox())!.width).toBeGreaterThan(950)
  100 |   expect((await page.getByTestId('search-map').boundingBox())!.height).toBeCloseTo(map.height,0)
  101 |   await page.setViewportSize({width:1920,height:1080})
  102 |   await expect.poll(async()=> (await page.getByTestId('search-map').boundingBox())!.width).toBeGreaterThan(950)
  103 |   const wideControls=(await page.locator('.acquisition-controls').boundingBox())!
  104 |   const wideMap=(await page.getByTestId('search-map').boundingBox())!
  105 |   expect(wideMap.width).toBeGreaterThan(wideControls.width*2)
  106 |   expect(wideMap.height).toBeGreaterThan(map.height+100)
  107 |   await page.locator('.workspace-content').evaluate(el=>{el.scrollTop=0})
  108 |   await page.screenshot({path:info.outputPath('layout-wide-zh-dark.png')})
  109 |   await page.setViewportSize({width:850,height:768})
  110 |   await expect.poll(async()=> {
  111 |     const c=(await page.locator('.acquisition-controls').boundingBox())!
  112 |     const m=(await page.getByTestId('search-map').boundingBox())!
  113 |     return m.y>=c.y+c.height
  114 |   }).toBe(true)
  115 | 
  116 | })
  117 | 
  118 | test('distinguishes partial imagery, clears recovered errors and excludes offscreen failures', async ({page}) => {
  119 |   let response:'partial'|'ready'|'failed'='partial', counter=0
  120 |   await page.route('**/api/v1/maps/imagery/**', route => {
  121 |     const fail=response==='failed' || (response==='partial' && ++counter%2===0)
  122 |     return fail?route.abort():route.fulfill({contentType:'image/png',body:png})
  123 |   })
  124 |   await page.getByRole('toolbar').getByRole('button',{name:'Explore',exact:true}).click()
  125 |   await expect(page.getByText('Some imagery tiles could not load',{exact:true})).toBeVisible()
  126 |   await expect(page.getByText('Imagery unavailable',{exact:true})).not.toBeVisible()
  127 |   response='ready'
  128 |   await page.getByRole('button',{name:'Retry imagery',exact:true}).click()
```