# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: p01-acquisition.spec.ts >> uses keyboard controls and keeps imagery failure recoverable in Chinese dark mode
- Location: e2e/p01-acquisition.spec.ts:76:1

# Error details

```
Test timeout of 30000ms exceeded.
```

```
Error: locator.click: Test timeout of 30000ms exceeded.
Call log:
  - waiting for getByRole('button', { name: '收起属性面板', exact: true })

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
      - generic [ref=e10]: 未打开工程
      - button "24 CPU" [ref=e11] [cursor=pointer]:
        - generic [aria-hidden] [ref=e12]: memory
      - button "下载" [ref=e14] [cursor=pointer]:
        - generic [ref=e15]:
          - img [aria-hidden] [ref=e16]: download
          - generic [ref=e17]: 下载
      - button "检索" [ref=e18] [cursor=pointer]:
        - generic [ref=e19]:
          - img [aria-hidden] [ref=e20]: travel_explore
          - generic [ref=e21]: 检索
      - button "Change language" [ref=e22] [cursor=pointer]:
        - img [aria-hidden] [ref=e24]: translate
      - button "Toggle theme" [ref=e25] [cursor=pointer]:
        - img [aria-hidden] [ref=e27]: light_mode
      - generic [ref=e28]:
        - status [ref=e29]: 后台运行中
        - button "退出应用" [ref=e31] [cursor=pointer]:
          - generic [ref=e32]:
            - img [aria-hidden] [ref=e33]: power_settings_new
            - generic [ref=e34]: 退出应用
  - main [ref=e36]:
    - generic [ref=e37]:
      - complementary [ref=e39]:
        - generic [ref=e40]:
          - generic [ref=e41]: 工程浏览器
          - button "首页" [ref=e42] [cursor=pointer]:
            - img [aria-hidden] [ref=e44]: home
        - generic [ref=e45]:
          - generic [aria-hidden] [ref=e46]: folder_open
          - paragraph [ref=e47]: 打开工程以查看数据和处理历史。
          - button "新建工程" [ref=e48] [cursor=pointer]
        - generic [ref=e51]:
          - button "下载任务" [ref=e52] [cursor=pointer]:
            - generic [ref=e53]:
              - img [aria-hidden] [ref=e54]: download
              - generic [ref=e55]: 下载任务
          - button "文件视图" [disabled] [ref=e56]:
            - generic [ref=e57]:
              - img [aria-hidden] [ref=e58]: folder
              - generic [ref=e59]: 文件视图
          - button "数据仓库" [ref=e60] [cursor=pointer]:
            - generic [ref=e61]:
              - img [aria-hidden] [ref=e62]: inventory_2
              - generic [ref=e63]: 数据仓库
      - separator "调整工程栏宽度" [ref=e64]
      - generic [ref=e67]:
        - main [ref=e70]:
          - tablist "工作流程页面" [ref=e71]:
            - generic [ref=e72]:
              - tab "1 检索与下载" [selected] [ref=e73] [cursor=pointer]
              - tab "2 数据与准备" [disabled] [ref=e77]
              - tab "3 参数与生成" [disabled] [ref=e81]
              - tab "4 运行" [disabled] [ref=e85]
              - tab "5 成果与 QC" [disabled] [ref=e89]
          - navigation "页内视图" [ref=e93]:
            - button "检索" [ref=e94] [cursor=pointer]
            - button "下载任务" [ref=e97] [cursor=pointer]
          - generic [ref=e101]:
            - generic [ref=e102]:
              - generic [ref=e103]:
                - generic [ref=e104]: SAR 数据检索
                - heading "为研究区域查找数据" [level=1] [ref=e105]
              - status [ref=e106]: ASF DAAC
            - generic [ref=e107]:
              - generic [ref=e108]:
                - heading "检索条件" [level=2] [ref=e109]
                - status [ref=e110]: Sentinel-1 · IW · SLC
                - generic [ref=e113] [cursor=pointer]:
                  - generic [ref=e114]:
                    - generic: 任务
                    - generic [ref=e115]:
                      - generic [ref=e116]: SENTINEL-1
                      - combobox "任务" [ref=e117]: SENTINEL-1
                  - generic [aria-hidden] [ref=e119]: arrow_drop_down
                - group "Sentinel-1 卫星 · 可多选" [ref=e120]:
                  - generic [ref=e122]:
                    - checkbox "SENTINEL-1A" [checked] [ref=e123] [cursor=pointer]:
                      - generic [ref=e128]: A
                    - checkbox "SENTINEL-1B" [checked] [ref=e129] [cursor=pointer]:
                      - generic [ref=e134]: B
                    - checkbox "SENTINEL-1C" [checked] [ref=e135] [cursor=pointer]:
                      - generic [ref=e140]: C
                    - checkbox "SENTINEL-1D" [checked] [ref=e141] [cursor=pointer]:
                      - generic [ref=e146]: D
                - generic [ref=e147]:
                  - generic [ref=e151]:
                    - generic: 开始日期 · UTC
                    - textbox "开始日期 · UTC" [ref=e152]: 2026-06-09
                  - generic [ref=e156]:
                    - generic: 结束日期 · UTC
                    - textbox "结束日期 · UTC" [ref=e157]: 2026-09-07
                - generic [ref=e160] [cursor=pointer]:
                  - generic [ref=e161]:
                    - generic: AOI 格式
                    - generic [ref=e162]:
                      - generic [ref=e163]: BBOX
                      - combobox "AOI 格式" [ref=e164]: BBOX
                  - generic [aria-hidden] [ref=e166]: arrow_drop_down
                - generic [ref=e170]:
                  - generic: 西、南、东、北
                  - textbox "西、南、东、北" [ref=e171]: 100,30,102,32
                - button "在地图上预览 AOI" [ref=e172] [cursor=pointer]:
                  - generic [ref=e173]:
                    - img [aria-hidden] [ref=e174]: center_focus_strong
                    - generic [ref=e175]: 在地图上预览 AOI
                - generic [ref=e178] [cursor=pointer]:
                  - generic [ref=e179]:
                    - generic: 轨道方向 · 可选
                    - combobox "轨道方向 · 可选" [ref=e181]
                  - generic [aria-hidden] [ref=e183]: arrow_drop_down
                - generic [ref=e187]:
                  - generic: 相对轨道 · 可选
                  - spinbutton "相对轨道 · 可选" [ref=e188]
                - generic [ref=e191] [cursor=pointer]:
                  - generic [ref=e192]:
                    - generic: 极化 · 可选
                    - combobox "极化 · 可选" [ref=e194]
                  - generic [aria-hidden] [ref=e196]: arrow_drop_down
                - generic [ref=e197]:
                  - button "检索 SAR 数据" [ref=e198] [cursor=pointer]:
                    - generic [ref=e199]:
                      - img [aria-hidden] [ref=e200]: search
                      - generic [ref=e201]: 检索 SAR 数据
                  - button "重置筛选" [ref=e202] [cursor=pointer]
              - generic [ref=e205]:
                - generic [ref=e206]:
                  - generic [ref=e207]:
                    - button "框选 AOI" [ref=e208] [cursor=pointer]
                    - button "定位覆盖范围" [ref=e211] [cursor=pointer]
                  - button "重试底图" [ref=e214] [cursor=pointer]
                  - generic [ref=e217]:
                    - generic:
                      - generic:
                        - img:
                          - generic:
                            - generic [ref=e218] [cursor=pointer]
                            - generic [ref=e219] [cursor=pointer]
                    - generic:
                      - generic [ref=e220]:
                        - button "Zoom in" [ref=e221] [cursor=pointer]: +
                        - button "Zoom out" [ref=e222] [cursor=pointer]: −
                      - generic [ref=e223]:
                        - link "Leaflet" [ref=e224] [cursor=pointer]:
                          - /url: https://leafletjs.com
                        - text: "| Tiles © Esri"
                  - generic: 底图加载失败
                - button "下载环境待配置" [ref=e230] [cursor=pointer]:
                  - generic [aria-hidden] [ref=e231]: info_outline
                  - generic [aria-hidden] [ref=e233]: expand_more
            - generic [ref=e234]:
              - generic [ref=e235]:
                - heading "检索结果 · 1" [level=2] [ref=e236]
                - generic [ref=e237]: SENTINEL-1 · 2026-06-09 — 2026-09-07
              - generic [ref=e238]:
                - button "全选已加载结果" [ref=e239] [cursor=pointer]
                - button "取消全选" [ref=e242] [cursor=pointer]
                - generic [ref=e245]: 0 项已选择 · 0.00 GiB
              - generic [ref=e246]:
                - table [ref=e248]:
                  - rowgroup [ref=e249]:
                    - row [ref=e250]:
                      - columnheader "Select all rows" [ref=e251]:
                        - checkbox "Select all rows" [ref=e252] [cursor=pointer]
                      - columnheader "卫星" [ref=e257] [cursor=pointer]:
                        - text: 卫星
                        - generic [aria-hidden] [ref=e258]: arrow_upward
                      - columnheader "成像时间（UTC）" [ref=e259] [cursor=pointer]:
                        - text: 成像时间（UTC）
                        - generic [aria-hidden] [ref=e260]: arrow_upward
                      - columnheader "相对轨道" [ref=e261] [cursor=pointer]:
                        - text: 相对轨道
                        - generic [aria-hidden] [ref=e262]: arrow_upward
                      - columnheader "轨道方向" [ref=e263]
                      - columnheader "极化" [ref=e264]
                      - columnheader "GiB" [ref=e265]
                      - columnheader "产品 ID" [ref=e266]
                  - rowgroup [ref=e267]:
                    - row [ref=e268] [cursor=pointer]:
                      - cell [ref=e269]:
                        - checkbox "Select row" [ref=e270]
                      - cell "SENTINEL-1D" [ref=e275]
                      - cell "2026-01-02T12:00:00Z" [ref=e276]
                      - cell [ref=e277]
                      - cell [ref=e278]
                      - cell "VV" [ref=e279]
                      - cell "0.00" [ref=e280]
                      - cell "S1D-first" [ref=e281]
                - generic [ref=e282]:
                  - generic [ref=e283]:
                    - generic [ref=e284]: "Records per page:"
                    - generic [ref=e287] [cursor=pointer]:
                      - generic [ref=e289]:
                        - generic [ref=e290]: "10"
                        - combobox "Records per page:" [ref=e291]: "10"
                      - generic [aria-hidden] [ref=e293]: arrow_drop_down
                  - generic [ref=e294]: 1–1 of 1
              - generic [ref=e296]:
                - button "已选清单 (0)" [ref=e297] [cursor=pointer]
                - button "仅下载" [disabled] [ref=e300]:
                  - generic [ref=e301]:
                    - img [aria-hidden] [ref=e302]: download
                    - generic [ref=e303]: 仅下载
                - button "从所选数据创建工程" [disabled] [ref=e304]
            - button "Expand \"网络设置\"" [ref=e309] [cursor=pointer]:
              - generic [ref=e310]: 网络设置
              - generic [aria-hidden] [ref=e313]: keyboard_arrow_down
        - complementary [ref=e314]:
          - button "展开属性面板" [ref=e315] [cursor=pointer]:
            - generic [aria-hidden] [ref=e316]: chevron_left
            - generic [ref=e317]: 属性
  - contentinfo [ref=e318]:
    - generic [ref=e319]:
      - generic [ref=e321]: 本机引擎
      - separator [ref=e322]
      - generic [ref=e323]: 0 个处理任务
      - button "任务" [ref=e324] [cursor=pointer]
      - button "下载任务" [ref=e327] [cursor=pointer]:
        - generic [ref=e328]:
          - img [aria-hidden] [ref=e329]: download
          - generic [ref=e330]: 下载任务
      - generic [ref=e331]: 未打开工程
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
  12 |  await expect(page.getByRole('heading',{name:'Recent projects',exact:true})).toBeVisible()
  13 |  await expect(page.locator('.global-progress')).not.toBeVisible()
  14 |  await page.getByRole('button',{name:'Explore',exact:true}).click()
  15 |  await page.getByLabel('West, south, east, north',{exact:true}).fill('100,30,102,32')
  16 |  await page.getByRole('button',{name:'Search SAR data',exact:true}).click()
  17 |  await expect(page.getByText('S1D-first',{exact:true})).toBeVisible()
  18 | })
  19 | 
  20 | test('retains a basket across searches and ignores an obsolete response',async({page})=>{
  21 |  const explorer=page.getByTestId('data-explorer')
  22 |  await explorer.getByRole('button',{name:'Select all loaded',exact:true}).click()
  23 |  let release:()=>void=()=>{}
  24 |  let calls=0
  25 |  await page.route('**/api/v1/data/search',async route=>{
  26 |   calls++
  27 |   if(calls===1){await new Promise<void>(resolve=>{release=resolve});await route.fulfill({json:group('obsolete')}).catch(()=>{});}
  28 |   else await route.fulfill({json:group('S1C-second')})
  29 |  })
  30 |  await explorer.getByRole('button',{name:'Search SAR data',exact:true}).click()
  31 |  await expect.poll(()=>calls).toBe(1)
  32 |  await explorer.getByLabel('Start date · UTC',{exact:true}).fill('2026-01-01')
  33 |  await explorer.getByRole('button',{name:'Search SAR data',exact:true}).click()
  34 |  await expect(explorer.getByText('S1C-second',{exact:true})).toBeVisible()
  35 |  release()
  36 |  await explorer.getByRole('button',{name:'Select all loaded',exact:true}).click()
  37 |  await explorer.getByRole('button',{name:'Selected scenes (2)',exact:true}).click()
  38 |  await expect(page.getByRole('dialog').getByText('S1D-first',{exact:true})).toBeVisible()
  39 |  await expect(page.getByRole('dialog').getByText('S1C-second',{exact:true})).toBeVisible()
  40 |  await page.keyboard.press('Escape')
  41 |  await expect(explorer.getByText('obsolete',{exact:true})).toHaveCount(0)
  42 | })
  43 | 
  44 | test('reviews all four EOF/DEM combinations and submits the frozen plan',async({page},info)=>{
  45 |  const requests:any[]=[]
  46 |  const commits:any[]=[]
  47 |  await page.route('**/api/v1/data/acquisition-preview',async route=>{
  48 |   const b=route.request().postDataJSON();requests.push(b)
  49 |   const roles=['SLC',...(b.include_orbits?['ORBIT']:[]),...(b.include_dem?['DEM']:[])]
  50 |   await route.fulfill({json:{plan_id:'review-'+requests.length,product_ids:b.product_ids,products:[product('S1D-first')],expected_revision:null,blockers:[],known_bytes:1024,unknown_files:roles.length-1,free_bytes:10*1024**3,destination:'/test/library',files:roles.map(role=>({file_id:role,role,scene_id:role==='DEM'?'COP30':'S1D-first',status:'planned'})),dem:b.include_dem?{geometry:polygon,tile_count:4,buffer_m:b.buffer_m}:null}})
  51 |  })
  52 |  await page.route('**/api/v1/data/acquisition-commit',async route=>{
  53 |   commits.push(route.request().postDataJSON())
  54 |   await route.fulfill({json:{project:null,job:{job_id:'new-attempt',status:'QUEUED'},plan_id:'review-4'}})
  55 |  })
  56 |  await page.getByRole('button',{name:'Select all loaded',exact:true}).click()
  57 |  await page.getByRole('button',{name:'Download only',exact:true}).click()
  58 |  const dialog=page.getByTestId('acquisition-dialog')
  59 |  for(const [orbits,dem] of [[false,false],[true,false],[false,true],[true,true]]){
  60 |   await dialog.getByRole('checkbox',{name:'Download precise EOF',exact:true}).setChecked(orbits!)
  61 |   await dialog.getByRole('checkbox',{name:'Download full-scene DEM',exact:true}).setChecked(dem!)
  62 |   await dialog.getByRole('button',{name:'Prepare review',exact:true}).click()
  63 |   await expect(dialog.getByRole('button',{name:'Start download',exact:true})).toBeEnabled()
  64 |   expect(requests.at(-1).include_orbits).toBe(orbits)
  65 |   expect(requests.at(-1).include_dem).toBe(dem)
  66 |   expect(requests.at(-1).buffer_m).toBe(20000)
  67 |  }
  68 |  await page.screenshot({path:info.outputPath('acquisition-review.png')})
  69 |  await dialog.getByRole('button',{name:'Start download',exact:true}).click()
  70 |  await expect(page.getByTestId('download-jobs')).toBeVisible()
  71 |  expect(commits).toHaveLength(1)
  72 |  expect(commits[0].plan_id).toBe('review-4')
  73 |  expect(commits[0].start_download).toBe(true)
  74 | })
  75 | 
  76 | test('uses keyboard controls and keeps imagery failure recoverable in Chinese dark mode',async({page},info)=>{
  77 |  await page.getByRole('button',{name:'Change language',exact:true}).click()
  78 |  await page.getByRole('button',{name:'Toggle theme',exact:true}).click()
> 79 |  await page.getByRole('button',{name:'收起属性面板',exact:true}).click()
     |                                                            ^ Error: locator.click: Test timeout of 30000ms exceeded.
  80 |  const explorer=page.getByTestId('data-explorer')
  81 |  await expect(explorer.getByRole('button',{name:'重试底图',exact:true})).toBeVisible()
  82 |  await explorer.getByRole('button',{name:'框选 AOI',exact:true}).click()
  83 |  await explorer.locator('.leaflet-host').focus()
  84 |  await page.keyboard.press('Escape')
  85 |  await expect(explorer.getByRole('button',{name:'框选 AOI',exact:true})).toBeVisible()
  86 |  expect(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth)).toBe(false)
  87 |  await page.screenshot({path:info.outputPath('p01-zh-dark.png')})
  88 | })
  89 | 
```