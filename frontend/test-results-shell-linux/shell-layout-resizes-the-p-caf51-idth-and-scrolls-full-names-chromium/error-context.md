# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: shell-layout.spec.ts >> resizes the project explorer, preserves width and scrolls full names
- Location: e2e/shell-layout.spec.ts:34:1

# Error details

```
Error: expect(received).toBeLessThan(expected)

Expected: < 3
Received:   77

Call Log:
- Timeout 5000ms exceeded while waiting on the predicate
```

# Page snapshot

```yaml
- generic [ref=f1e3]:
  - banner [ref=f1e4]:
    - toolbar [ref=f1e5]:
      - generic [ref=f1e6] [cursor=pointer]:
        - img "InSAR-PILOT logo" [ref=f1e7]
        - generic [ref=f1e8]: InSAR-PILOT
        - generic [ref=f1e9]: NEXT
      - separator [ref=f1e10]
      - generic [ref=f1e11]: Picker existing
      - button "24 CPU" [ref=f1e12] [cursor=pointer]:
        - generic [aria-hidden] [ref=f1e13]: memory
      - button "Downloads" [ref=f1e15] [cursor=pointer]:
        - generic [ref=f1e16]:
          - img [aria-hidden] [ref=f1e17]: download
          - generic [ref=f1e18]: Downloads
      - button "Explore" [ref=f1e19] [cursor=pointer]:
        - generic [ref=f1e20]:
          - img [aria-hidden] [ref=f1e21]: travel_explore
          - generic [ref=f1e22]: Explore
      - button "Hide properties panel" [expanded] [ref=f1e23] [cursor=pointer]:
        - img [aria-hidden] [ref=f1e25]: chevron_right
      - button "Change language" [ref=f1e26] [cursor=pointer]:
        - img [aria-hidden] [ref=f1e28]: translate
      - button "Toggle theme" [ref=f1e29] [cursor=pointer]:
        - img [aria-hidden] [ref=f1e31]: dark_mode
      - generic [ref=f1e32]:
        - status [ref=f1e33]: Backend running
        - button "Exit app" [ref=f1e35] [cursor=pointer]:
          - generic [ref=f1e36]:
            - img [aria-hidden] [ref=f1e37]: power_settings_new
            - generic [ref=f1e38]: Exit app
  - main [ref=f1e40]:
    - generic [ref=f1e41]:
      - complementary [ref=f1e43]:
        - generic [ref=f1e44]:
          - generic [ref=f1e45]: PROJECT EXPLORER
          - button "Home" [ref=f1e46] [cursor=pointer]:
            - img [aria-hidden] [ref=f1e48]: home
        - generic "Project tree · scroll to read full names" [ref=f1e49]:
          - tree [ref=f1e50]:
            - generic [ref=f1e51]:
              - treeitem "Picker existing" [expanded] [ref=f1e52] [cursor=pointer]:
                - generic [aria-hidden] [ref=f1e53]: play_arrow
                - generic "Picker existing" [ref=f1e55]
              - group [ref=f1e57]:
                - generic [ref=f1e58]:
                  - treeitem "Data" [expanded] [selected] [ref=f1e59] [cursor=pointer]:
                    - generic [aria-hidden] [ref=f1e60]: play_arrow
                    - generic "Data" [ref=f1e62]
                  - group [ref=f1e64]:
                    - treeitem "S1D_IW_SLC__long_acquisition_name_long_acquisition_name_long_acquisition_name_long_acquisition_name_long_acquisition_name_long_acquisition_name_long_acquisition_name_long_acquisition_name_long_acquisition_name_long_acquisition_name_long_acquisition_name_long_acquisition_name_long_acquisition_name_long_acquisition_name_" [ref=f1e66] [cursor=pointer]:
                      - generic "S1D_IW_SLC__long_acquisition_name_long_acquisition_name_long_acquisition_name_long_acquisition_name_long_acquisition_name_long_acquisition_name_long_acquisition_name_long_acquisition_name_long_acquisition_name_long_acquisition_name_long_acquisition_name_long_acquisition_name_long_acquisition_name_long_acquisition_name_" [ref=f1e68]
                - treeitem "Processing" [ref=f1e70] [cursor=pointer]:
                  - generic "Processing" [ref=f1e72]
                - treeitem "Products" [ref=f1e74] [cursor=pointer]:
                  - generic "Products" [ref=f1e76]
                - treeitem "QC" [ref=f1e78] [cursor=pointer]:
                  - generic "QC" [ref=f1e80]
                - treeitem "Run history" [ref=f1e82] [cursor=pointer]:
                  - generic "Run history" [ref=f1e84]
                - treeitem "Events" [ref=f1e86] [cursor=pointer]:
                  - generic "Events" [ref=f1e88]
                - treeitem "Post-processing" [ref=f1e90] [cursor=pointer]:
                  - generic "Post-processing" [ref=f1e92]
        - generic [ref=f1e93]:
          - button "Downloads" [ref=f1e94] [cursor=pointer]:
            - generic [ref=f1e95]:
              - img [aria-hidden] [ref=f1e96]: download
              - generic [ref=f1e97]: Downloads
          - button "Files view" [ref=f1e98] [cursor=pointer]:
            - generic [ref=f1e99]:
              - img [aria-hidden] [ref=f1e100]: folder
              - generic [ref=f1e101]: Files view
          - button "Data Library" [ref=f1e102] [cursor=pointer]:
            - generic [ref=f1e103]:
              - img [aria-hidden] [ref=f1e104]: inventory_2
              - generic [ref=f1e105]: Data Library
      - separator "Resize project explorer" [ref=f1e106]
      - generic [ref=f1e109]:
        - main [ref=f1e111]:
          - tablist "Workflow pages" [ref=f1e112]:
            - generic [ref=f1e113]:
              - tab "1 Search & download" [ref=f1e114] [cursor=pointer]
              - tab "2 Data & preparation" [selected] [ref=f1e118] [cursor=pointer]
              - tab "3 Parameters & generation" [ref=f1e122] [cursor=pointer]
              - tab "4 Run" [ref=f1e126] [cursor=pointer]
              - tab "5 Products & QC" [ref=f1e130] [cursor=pointer]
          - generic [ref=f1e135]:
            - heading "Project data" [level=1] [ref=f1e136]
            - paragraph [ref=f1e137]: Reference existing files without copying SAR inputs into each project.
            - generic [ref=f1e140] [cursor=pointer]:
              - generic [ref=f1e141]:
                - generic: Input role
                - generic [ref=f1e142]:
                  - generic [ref=f1e143]: sar
                  - combobox "Input role" [ref=f1e144]: sar
              - generic [aria-hidden] [ref=f1e146]: arrow_drop_down
            - generic [ref=f1e150]:
              - generic [ref=f1e151]:
                - generic: Input files or SAFE folders · one per line
                - textbox "Input files or SAFE folders · one per line" [ref=f1e152]
              - 'button "Browse: Input files or SAFE folders · one per line" [ref=f1e154] [cursor=pointer]':
                - generic [ref=f1e155]:
                  - img [aria-hidden] [ref=f1e156]: folder_open
                  - generic [ref=f1e157]: Browse
            - generic [ref=f1e158]:
              - button "Import references" [ref=f1e159] [cursor=pointer]
              - button "Attach processing dataset" [ref=f1e162] [cursor=pointer]
            - list [ref=f1e165]:
              - button "Sentinel1SLC sentinel1_tops" [ref=f1e166] [cursor=pointer]:
                - generic [ref=f1e167]: Sentinel1SLC
                - generic [ref=f1e169]: sentinel1_tops
        - separator "Resize" [ref=f1e170]
        - complementary [ref=f1e173]:
          - generic [ref=f1e174]:
            - generic [ref=f1e175]: INSPECTOR
            - button "Collapse properties panel" [ref=f1e176] [cursor=pointer]:
              - img [aria-hidden] [ref=f1e178]: chevron_right
          - heading "Object details" [level=3] [ref=f1e179]
          - tablist [ref=f1e180]:
            - generic [ref=f1e181]:
              - tab "Properties" [selected] [ref=f1e182] [cursor=pointer]
              - tab "QC" [ref=f1e186] [cursor=pointer]
              - tab "History" [ref=f1e190] [cursor=pointer]
          - generic [ref=f1e194]:
            - generic [aria-hidden] [ref=f1e195]: touch_app
            - paragraph [ref=f1e196]: Select a step, run or artifact to inspect its properties and provenance.
  - contentinfo [ref=f1e197]:
    - generic [ref=f1e198]:
      - generic [ref=f1e200]: Local engine
      - separator [ref=f1e201]
      - generic [ref=f1e202]: 0 processing jobs
      - button "Jobs" [ref=f1e203] [cursor=pointer]
      - button "Downloads" [ref=f1e206] [cursor=pointer]:
        - generic [ref=f1e207]:
          - img [aria-hidden] [ref=f1e208]: download
          - generic [ref=f1e209]: Downloads
      - generic [ref=f1e210]: unassigned
```

# Test source

```ts
  1  | import { expect, test } from '@playwright/test'
  2  | 
  3  | const png = Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=', 'base64')
  4  | test.beforeEach(async ({page}) => {
  5  |   await page.addInitScript(() => {
  6  |     if (!sessionStorage.getItem('shell-init')) {localStorage.clear();sessionStorage.setItem('shell-init','1')}
  7  |     sessionStorage.setItem('pilot-token','local-picker-test-session')
  8  |   })
  9  |   await page.route('**/api/v1/maps/imagery/**', route => route.fulfill({contentType:'image/png',body:png}))
  10 |   await page.route('**/api/v1/data/download-readiness', route => route.fulfill({json:{aria2_available:true,credentials_configured:true,gdal_available:true,library_path:'/fixture/library',aria2_executable:'/usr/bin/aria2c'}}))
  11 |   await page.goto('/')
  12 |   await expect(page.getByRole('heading',{name:'Recent projects',exact:true})).toBeVisible()
  13 | })
  14 | 
  15 | test('keeps five fixed pages across auxiliary views and project selection', async ({page}) => {
  16 |   const primary=page.getByTestId('primary-pages')
  17 |   await expect(primary.getByRole('tab')).toHaveCount(5)
  18 |   await expect(primary.getByRole('tab',{name:'2 Data & preparation'})).toBeDisabled()
  19 |   for (let i=0;i<2;i++) {
  20 |     await page.getByRole('toolbar').getByRole('button',{name:'Explore',exact:true}).click()
  21 |     await page.getByRole('toolbar').getByRole('button',{name:'Downloads',exact:true}).click()
  22 |     await page.getByRole('button',{name:'Home',exact:true}).click()
  23 |   }
  24 |   await page.locator('.project-card').filter({hasText:'Picker existing'}).click()
  25 |   for (const name of ['3 Parameters & generation','4 Run','5 Products & QC','2 Data & preparation']) {
  26 |     await primary.getByRole('tab',{name,exact:true}).click()
  27 |     await expect(primary.getByRole('tab',{name,exact:true})).toHaveAttribute('aria-selected','true')
  28 |   }
  29 |   await expect(primary.getByRole('tab')).toHaveCount(5)
  30 |   await page.getByRole('button',{name:'Home',exact:true}).click()
  31 |   await expect(primary.getByRole('tab')).toHaveCount(5)
  32 | })
  33 | 
  34 | test('resizes the project explorer, preserves width and scrolls full names', async ({page},info) => {
  35 |   const longName='S1D_IW_SLC__'+ 'long_acquisition_name_'.repeat(14)
  36 |   await page.route('**/api/v1/projects/*/artifacts', route=>route.fulfill({json:[{artifact_id:'long-source',created_by_run:null,type:'Sentinel1SLC',metadata:{native_product_id:longName},assets:[],mission:'sentinel1_tops'}]}))
  37 |   await page.locator('.project-card').filter({hasText:'Picker existing'}).click()
  38 |   const tree=page.locator('.project-tree-scroll')
  39 |   await expect(tree.getByText(longName,{exact:true})).toBeVisible()
  40 |   expect(await tree.evaluate(el=>el.scrollWidth>el.clientWidth)).toBe(true)
  41 |   await tree.evaluate(el=>{el.scrollLeft=300})
  42 |   expect(await tree.evaluate(el=>el.scrollLeft)).toBeGreaterThan(200)
  43 |   const separator=page.getByRole('separator',{name:'Resize project explorer'})
  44 |   const before=(await page.locator('.explorer').boundingBox())!.width
  45 |   const b=(await separator.boundingBox())!
  46 |   await page.mouse.move(b.x+b.width/2,b.y+100);await page.mouse.down()
  47 |   await page.mouse.move(b.x+80,b.y+100,{steps:12});await page.mouse.up()
  48 |   await expect.poll(async()=> (await page.locator('.explorer').boundingBox())!.width).toBeGreaterThan(before+50)
  49 |   const width=(await page.locator('.explorer').boundingBox())!.width
  50 |   await page.reload()
> 51 |   await expect.poll(async()=> Math.abs((await page.locator('.explorer').boundingBox())!.width-width)).toBeLessThan(3)
     |                                                                                                       ^ Error: expect(received).toBeLessThan(expected)
  52 |   await separator.focus();await page.keyboard.press('ArrowLeft')
  53 |   await expect.poll(async()=> (await page.locator('.explorer').boundingBox())!.width).toBeLessThan(width-5)
  54 |   await page.screenshot({path:info.outputPath('explorer-width.png')})
  55 | })
  56 | 
  57 | test('balances map and filters and keeps environment details collapsed', async ({page},info) => {
  58 |   await page.getByRole('toolbar').getByRole('button',{name:'Explore',exact:true}).click()
  59 |   const summary=page.locator('.readiness-summary')
  60 |   await expect(summary).toHaveAttribute('aria-expanded','false')
  61 |   await expect(summary).toContainText('Download environment configured')
  62 |   const controls=(await page.locator('.acquisition-controls').boundingBox())!
  63 |   const map=(await page.getByTestId('search-map').first().boundingBox())!
  64 |   expect(Math.abs(map.width-controls.width)).toBeLessThan(3)
  65 |   expect(map.width/map.height).toBeGreaterThan(1.25)
  66 |   await summary.click()
  67 |   await expect(page.getByText('/fixture/library',{exact:true})).toBeVisible()
  68 |   await summary.click()
  69 |   await expect(page.getByText('/fixture/library',{exact:true})).not.toBeVisible()
  70 |   await page.screenshot({path:info.outputPath('layout-en.png')})
  71 |   await page.getByRole('button',{name:'Change language',exact:true}).click()
  72 |   await page.getByRole('button',{name:'Toggle theme',exact:true}).click()
  73 |   await expect(page.getByTestId('primary-pages').getByRole('tab')).toHaveCount(5)
  74 |   await page.screenshot({path:info.outputPath('layout-zh-dark.png')})
  75 | })
  76 | 
  77 | test('distinguishes partial imagery, clears recovered errors and excludes offscreen failures', async ({page}) => {
  78 |   let response:'partial'|'ready'|'failed'='partial', counter=0
  79 |   await page.route('**/api/v1/maps/imagery/**', route => {
  80 |     const fail=response==='failed' || (response==='partial' && ++counter%2===0)
  81 |     return fail?route.abort():route.fulfill({contentType:'image/png',body:png})
  82 |   })
  83 |   await page.getByRole('toolbar').getByRole('button',{name:'Explore',exact:true}).click()
  84 |   await expect(page.getByText('Some imagery tiles could not load',{exact:true})).toBeVisible()
  85 |   await expect(page.getByText('Imagery unavailable',{exact:true})).not.toBeVisible()
  86 |   response='ready'
  87 |   await page.getByRole('button',{name:'Retry imagery',exact:true}).click()
  88 |   await expect(page.getByTestId('search-map')).toHaveAttribute('data-imagery-state','ready')
  89 |   response='failed'
  90 |   await page.locator('.leaflet-control-zoom-in').click()
  91 |   await expect(page.getByText('Imagery unavailable',{exact:true})).toBeVisible()
  92 |   response='ready'
  93 |   await expect(page.locator('.leaflet-zoom-anim')).toHaveCount(0)
  94 |   await page.locator('.leaflet-control-zoom-in').click()
  95 |   await expect(page.getByTestId('search-map')).toHaveAttribute('data-imagery-state','ready')
  96 |   await expect(page.locator('.imagery-notice')).not.toBeVisible()
  97 | })
  98 | 
```