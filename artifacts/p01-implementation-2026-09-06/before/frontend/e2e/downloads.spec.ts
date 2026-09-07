import { expect, test } from '@playwright/test'

function fixture() {
  return {job_id:'fixture-transfer',status:'RUNNING',display_status:'RUNNING',cancel_requested:false,created_at:'2026-09-05T12:00:00Z',products:[
    {remote_product_id:'S1A_IW_SLC__1SDV_20260901_REFERENCE_LONG_PRODUCT_NAME',mission:'SENTINEL-1',acquisition_time:'2026-09-01T00:00:00Z'},
    {remote_product_id:'S1C_IW_SLC__1SDV_20260904_SECONDARY_LONG_PRODUCT_NAME',mission:'SENTINEL-1',acquisition_time:'2026-09-04T00:00:00Z'},
  ],progress:[],results:[],destination:'/home/griffin/shared library/Sentinel1'}
}

test('download queue remains discoverable after refresh and shows every planned acquisition', async ({page}, info) => {
  await page.route('**/api/v1/data/downloads', route=>route.fulfill({json:[fixture()]}))
  await page.goto('/#token=local-picker-test-session')
  await page.getByRole('button',{name:'Downloads',exact:true}).first().click()
  const downloads = page.getByTestId('download-jobs')
  await expect(downloads.getByText(fixture().products[0].remote_product_id,{exact:true})).toHaveCount(2)
  await expect(downloads.getByText(fixture().products[1].remote_product_id,{exact:true})).toHaveCount(2)
  await expect(downloads.getByText('EOF',{exact:true})).toHaveCount(2)
  await expect(downloads.getByRole('button',{name:'Pause',exact:true})).toBeVisible()
  await page.reload()
  await page.getByRole('button',{name:'Jobs',exact:true}).click()
  await expect(page.getByTestId('download-jobs')).toContainText('2 acquisitions')
  await page.evaluate(()=>{localStorage.setItem('pilot-language','zh');localStorage.setItem('pilot-dark','true')})
  await page.reload()
  await page.getByRole('button',{name:'下载任务',exact:true}).first().click()
  await expect(page.getByTestId('download-jobs').getByRole('button',{name:'暂停',exact:true})).toBeVisible()
  expect(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth)).toBe(false)
  await page.screenshot({path:info.outputPath('downloads-zh-dark.png')})
})

test('pause, resume, cancel and retry expose real controls and retain linked history', async ({page}) => {
  let jobs: any[] = [fixture()]
  const actions: string[] = []
  await page.route('**/api/v1/data/downloads', route=>route.fulfill({json:jobs}))
  await page.route('**/api/v1/data/downloads/*/*', async route=>{
    const [,id,action] = /downloads\/([^/]+)\/([^/]+)$/.exec(route.request().url())!
    actions.push(action)
    const job = jobs.find(j=>j.job_id===id)
    if (action==='pause') Object.assign(job,{status:'CANCELLED',display_status:'PAUSED',cancel_requested:true})
    if (action==='cancel') Object.assign(job,{status:'CANCELLED',display_status:'CANCELLED',cancel_requested:true})
    if (['resume','retry'].includes(action)) {
      const child={...fixture(),job_id:`child-${actions.length}`,parent_job_id:id}
      Object.assign(job,{display_status:'CONTINUED',continued_by:child.job_id})
      jobs=[child,...jobs]
    }
    await route.fulfill({json:jobs[0]})
  })
  await page.goto('/#token=local-picker-test-session')
  await page.getByRole('button',{name:'Downloads',exact:true}).first().click()
  const downloads = page.getByTestId('download-jobs')
  await downloads.getByRole('button',{name:'Pause',exact:true}).click()
  await expect(downloads.getByText('Paused',{exact:true})).toBeVisible()
  await downloads.getByRole('button',{name:'Resume',exact:true}).click()
  await expect(downloads.locator('[data-job-id]')).toHaveCount(2)
  await downloads.getByRole('button',{name:'Cancel download',exact:true}).click()
  await expect(downloads.getByText('Cancelled',{exact:true})).toBeVisible()
  await downloads.getByRole('button',{name:'Retry',exact:true}).click()
  await expect(downloads.locator('[data-job-id]')).toHaveCount(3)
  expect(actions).toEqual(['pause','resume','cancel','retry'])
})
