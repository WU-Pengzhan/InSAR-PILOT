# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: shell-layout.spec.ts >> gives the map more width and keeps environment details collapsed
- Location: e2e/shell-layout.spec.ts:65:1

# Error details

```
Error: expect(locator).toBeFocused() failed

Locator:  getByRole('button', { name: 'Hide properties panel', exact: true })
Expected: focused
Received: inactive
Timeout:  5000ms

Call log:
  - Expect "toBeFocused" getByRole('button', { name: 'Hide properties panel', exact: true }) with timeout 5000ms
  - waiting for getByRole('button', { name: 'Hide properties panel', exact: true })
    14 × locator resolved to <button tabindex="0" type="button" aria-expanded="true" aria-controls="properties-panel" aria-label="Hide properties panel" class="q-btn q-btn-item non-selectable no-outline q-btn--flat q-btn--rectangle q-btn--actionable q-focusable q-hoverable q-btn--dense">…</button>
       - unexpected value "inactive"

```

```yaml
- button "Hide properties panel" [expanded]
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
  28  |   await primary.getByRole('tab',{name:'3 Parameters & generation',exact:true}).click()
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
> 85  |   await expect(page.getByRole('button',{name:'Hide properties panel',exact:true})).toBeFocused()
      |                                                                                    ^ Error: expect(locator).toBeFocused() failed
  86  |   await expect(page.locator('.inspector')).toBeVisible()
  87  |   await summary.click()
  88  |   await expect(page.getByText('/fixture/library',{exact:true})).toBeVisible()
  89  |   await summary.click()
  90  |   await expect(page.getByText('/fixture/library',{exact:true})).not.toBeVisible()
  91  |   await page.screenshot({path:info.outputPath('layout-en.png')})
  92  |   await page.getByRole('button',{name:'Change language',exact:true}).click()
  93  |   await page.getByRole('button',{name:'Toggle theme',exact:true}).click()
  94  |   await expect(page.getByTestId('primary-pages').getByRole('tab')).toHaveCount(5)
  95  |   await page.screenshot({path:info.outputPath('layout-zh-dark.png')})
  96  |   await page.getByRole('button',{name:'收起属性面板',exact:true}).first().click()
  97  |   await page.setViewportSize({width:1920,height:768})
  98  |   await expect.poll(async()=> (await page.getByTestId('search-map').boundingBox())!.width).toBeGreaterThan(950)
  99  |   expect((await page.getByTestId('search-map').boundingBox())!.height).toBeCloseTo(map.height,0)
  100 |   await page.setViewportSize({width:1920,height:1080})
  101 |   await expect.poll(async()=> (await page.getByTestId('search-map').boundingBox())!.width).toBeGreaterThan(950)
  102 |   const wideControls=(await page.locator('.acquisition-controls').boundingBox())!
  103 |   const wideMap=(await page.getByTestId('search-map').boundingBox())!
  104 |   expect(wideMap.width).toBeGreaterThan(wideControls.width*2)
  105 |   expect(wideMap.height).toBeGreaterThan(map.height+100)
  106 |   await page.screenshot({path:info.outputPath('layout-wide-zh-dark.png')})
  107 |   await page.setViewportSize({width:850,height:768})
  108 |   await expect.poll(async()=> {
  109 |     const c=(await page.locator('.acquisition-controls').boundingBox())!
  110 |     const m=(await page.getByTestId('search-map').boundingBox())!
  111 |     return m.y>=c.y+c.height
  112 |   }).toBe(true)
  113 | 
  114 | })
  115 | 
  116 | test('distinguishes partial imagery, clears recovered errors and excludes offscreen failures', async ({page}) => {
  117 |   let response:'partial'|'ready'|'failed'='partial', counter=0
  118 |   await page.route('**/api/v1/maps/imagery/**', route => {
  119 |     const fail=response==='failed' || (response==='partial' && ++counter%2===0)
  120 |     return fail?route.abort():route.fulfill({contentType:'image/png',body:png})
  121 |   })
  122 |   await page.getByRole('toolbar').getByRole('button',{name:'Explore',exact:true}).click()
  123 |   await expect(page.getByText('Some imagery tiles could not load',{exact:true})).toBeVisible()
  124 |   await expect(page.getByText('Imagery unavailable',{exact:true})).not.toBeVisible()
  125 |   response='ready'
  126 |   await page.getByRole('button',{name:'Retry imagery',exact:true}).click()
  127 |   await expect(page.getByTestId('search-map')).toHaveAttribute('data-imagery-state','ready')
  128 |   response='failed'
  129 |   await page.locator('.leaflet-control-zoom-in').click()
  130 |   await expect(page.getByText('Imagery unavailable',{exact:true})).toBeVisible()
  131 |   response='ready'
  132 |   await expect(page.locator('.leaflet-zoom-anim')).toHaveCount(0)
  133 |   await page.locator('.leaflet-control-zoom-in').click()
  134 |   await expect(page.getByTestId('search-map')).toHaveAttribute('data-imagery-state','ready')
  135 |   await expect(page.locator('.imagery-notice')).not.toBeVisible()
  136 | })
  137 | 
```