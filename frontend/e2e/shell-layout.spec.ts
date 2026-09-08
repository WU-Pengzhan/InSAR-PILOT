import { expect, test } from '@playwright/test'

const png = Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=', 'base64')
test.beforeEach(async ({page}) => {
  await page.addInitScript(() => {
    if (!sessionStorage.getItem('shell-init')) {localStorage.clear();localStorage.setItem('pilot-inspector-collapsed','false');sessionStorage.setItem('shell-init','1')}
    sessionStorage.setItem('pilot-token','local-picker-test-session')
  })
  await page.route('**/api/v1/maps/imagery/**', route => route.fulfill({contentType:'image/png',body:png}))
  await page.route('**/api/v1/data/download-readiness', route => route.fulfill({json:{aria2_available:true,credentials_configured:true,gdal_available:true,library_path:'/fixture/library',aria2_executable:'/usr/bin/aria2c'}}))
  await page.goto('/')
  await expect(page.getByRole('heading',{name:'Recent projects',exact:true})).toBeVisible()
})

test('keeps five fixed pages across auxiliary views and project selection', async ({page}) => {
  const primary=page.getByTestId('primary-pages')
  await expect(primary.getByRole('tab')).toHaveCount(5)
  await expect(primary.getByRole('tab',{name:'2 Data & preparation'})).toBeDisabled()
  for (let i=0;i<2;i++) {
    await page.getByRole('toolbar').getByRole('button',{name:'Explore',exact:true}).click()
    await page.getByRole('toolbar').getByRole('button',{name:'Downloads',exact:true}).click()
    await page.getByRole('button',{name:'Home',exact:true}).click()
  }
  let release!:()=>void
  const pending=new Promise<void>(resolve=>{release=resolve})
  await page.route('**/api/v1/projects/open',async route=>{await pending;await route.continue()})
  await page.locator('.project-card').filter({hasText:'Picker existing'}).click()
  await expect(primary.getByRole('tab',{name:'3 Parameters & generation',exact:true})).toBeDisabled()
  await primary.getByRole('tab',{name:'1 Search & download',exact:true}).click()
  release()
  await expect(page.locator('.global-progress')).not.toBeVisible()
  await expect(primary.getByRole('tab',{name:'1 Search & download',exact:true})).toHaveAttribute('aria-selected','true')
  for (const name of ['3 Parameters & generation','4 Run','5 Products & QC','2 Data & preparation']) {
    await primary.getByRole('tab',{name,exact:true}).click()
    await expect(primary.getByRole('tab',{name,exact:true})).toHaveAttribute('aria-selected','true')
  }
  await expect(primary.getByRole('tab')).toHaveCount(5)
  await page.getByRole('button',{name:'Home',exact:true}).click()
  await expect(primary.getByRole('tab')).toHaveCount(5)
})

test('resizes the project explorer, preserves width and scrolls full names', async ({page},info) => {
  const longName='S1D_IW_SLC__'+ 'long_acquisition_name_'.repeat(14)
  await page.route('**/api/v1/projects/*/artifacts', route=>route.fulfill({json:[{artifact_id:'long-source',created_by_run:null,type:'Sentinel1SLC',metadata:{native_product_id:longName},assets:[],mission:'sentinel1_tops'}]}))
  await page.locator('.project-card').filter({hasText:'Picker existing'}).click()
  const tree=page.locator('.project-tree-scroll')
  await expect(tree.getByText(longName,{exact:true})).toBeVisible()
  expect(await tree.evaluate(el=>el.scrollWidth>el.clientWidth)).toBe(true)
  await tree.evaluate(el=>{el.scrollLeft=300})
  expect(await tree.evaluate(el=>el.scrollLeft)).toBeGreaterThan(200)
  const separator=page.getByRole('separator',{name:'Resize project explorer'})
  const before=(await page.locator('.explorer').boundingBox())!.width
  const b=(await separator.boundingBox())!
  await page.mouse.move(b.x+b.width/2,b.y+100);await page.mouse.down()
  await page.mouse.move(b.x+80,b.y+100,{steps:12});await page.mouse.up()
  await expect.poll(async()=> (await page.locator('.explorer').boundingBox())!.width).toBeGreaterThan(before+50)
  const width=(await page.locator('.explorer').boundingBox())!.width
  await expect.poll(async()=>Math.abs(Number(await page.evaluate(()=>localStorage.getItem('pilot-explorer-width')))-width)).toBeLessThan(3)
  await page.reload()
  await expect.poll(async()=> Math.abs((await page.locator('.explorer').boundingBox())!.width-width)).toBeLessThan(3)
  await separator.focus();await page.keyboard.press('ArrowLeft')
  await expect.poll(async()=> (await page.locator('.explorer').boundingBox())!.width).toBeLessThan(width-5)
  await page.screenshot({path:info.outputPath('explorer-width.png')})
})

test('gives the map more width and keeps environment details collapsed', async ({page},info) => {
  await page.getByRole('toolbar').getByRole('button',{name:'Explore',exact:true}).click()
  const summary=page.locator('.readiness-summary')
  await expect(summary).toHaveAttribute('aria-expanded','false')
  await expect(summary).toContainText('Download environment configured')
  const controls=(await page.locator('.acquisition-controls').boundingBox())!
  const map=(await page.getByTestId('search-map').first().boundingBox())!
  expect(controls.width).toBeLessThanOrEqual(341)
  expect(map.width).toBeGreaterThan(controls.width)
  await expect(page.getByRole('button',{name:/Hide filters|Show filters/})).toHaveCount(0)
  await expect(page.getByRole('toolbar').getByRole('button',{name:/properties panel/})).toHaveCount(0)
  await page.getByRole('button',{name:'Hide properties panel',exact:true}).click()
  const reopen=page.locator('.inspector-rail').getByRole('button',{name:'Show properties panel',exact:true})
  await expect(reopen).toBeFocused()
  await expect(reopen).toHaveAttribute('aria-expanded','false')
  const rail=(await page.locator('.inspector-rail').boundingBox())!
  expect(rail.x+rail.width).toBeCloseTo(1366,0)
  await expect.poll(async()=> (await page.getByTestId('search-map').boundingBox())!.width).toBeGreaterThan(map.width+100)
  expect((await page.getByTestId('search-map').boundingBox())!.height).toBeCloseTo(map.height,0)
  await page.keyboard.press('Enter')
  await expect(page.getByRole('button',{name:'Hide properties panel',exact:true})).toBeFocused()
  await expect(page.locator('.inspector')).toBeVisible()
  await summary.click()
  await expect(page.getByText('/fixture/library',{exact:true})).toBeVisible()
  await summary.click()
  await expect(page.getByText('/fixture/library',{exact:true})).not.toBeVisible()
  await page.locator('.workspace-content').evaluate(el=>{el.scrollTop=0})
  await page.screenshot({path:info.outputPath('layout-en.png')})
  await page.getByRole('button',{name:'Change language',exact:true}).click()
  await page.getByRole('button',{name:'Toggle theme',exact:true}).click()
  await expect(page.getByTestId('primary-pages').getByRole('tab')).toHaveCount(5)
  await page.screenshot({path:info.outputPath('layout-zh-dark.png')})
  await page.getByRole('button',{name:'收起属性面板',exact:true}).first().click()
  await page.setViewportSize({width:1920,height:768})
  await expect.poll(async()=> (await page.getByTestId('search-map').boundingBox())!.width).toBeGreaterThan(950)
  expect((await page.getByTestId('search-map').boundingBox())!.height).toBeCloseTo(map.height,0)
  await page.setViewportSize({width:1920,height:1080})
  await expect.poll(async()=> (await page.getByTestId('search-map').boundingBox())!.width).toBeGreaterThan(950)
  const wideControls=(await page.locator('.acquisition-controls').boundingBox())!
  const wideMap=(await page.getByTestId('search-map').boundingBox())!
  expect(wideMap.width).toBeGreaterThan(wideControls.width*2)
  expect(wideMap.height).toBeGreaterThan(map.height+100)
  await page.locator('.workspace-content').evaluate(el=>{el.scrollTop=0})
  await page.screenshot({path:info.outputPath('layout-wide-zh-dark.png')})
  await page.setViewportSize({width:850,height:768})
  await expect.poll(async()=> {
    const c=(await page.locator('.acquisition-controls').boundingBox())!
    const m=(await page.getByTestId('search-map').boundingBox())!
    return m.y>=c.y+c.height
  }).toBe(true)

})

test('distinguishes partial imagery, clears recovered errors and excludes offscreen failures', async ({page}) => {
  let response:'partial'|'ready'|'failed'='partial', counter=0
  await page.route('**/api/v1/maps/imagery/**', route => {
    const fail=response==='failed' || (response==='partial' && ++counter%2===0)
    return fail?route.abort():route.fulfill({contentType:'image/png',body:png})
  })
  await page.getByRole('toolbar').getByRole('button',{name:'Explore',exact:true}).click()
  await expect(page.getByText('Some imagery tiles could not load',{exact:true})).toBeVisible()
  await expect(page.getByText('Imagery unavailable',{exact:true})).not.toBeVisible()
  response='ready'
  await page.getByRole('button',{name:'Retry imagery',exact:true}).click()
  await expect(page.getByTestId('search-map')).toHaveAttribute('data-imagery-state','ready')
  response='failed'
  await page.locator('.leaflet-control-zoom-in').click()
  await expect(page.getByText('Imagery unavailable',{exact:true})).toBeVisible()
  response='ready'
  await expect(page.locator('.leaflet-zoom-anim')).toHaveCount(0)
  await page.locator('.leaflet-control-zoom-in').click()
  await expect(page.getByTestId('search-map')).toHaveAttribute('data-imagery-state','ready')
  await expect(page.locator('.imagery-notice')).not.toBeVisible()
})
