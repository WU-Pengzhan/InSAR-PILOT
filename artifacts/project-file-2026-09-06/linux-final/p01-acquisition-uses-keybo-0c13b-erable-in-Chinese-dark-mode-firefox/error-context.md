# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: p01-acquisition.spec.ts >> uses keyboard controls and keeps imagery failure recoverable in Chinese dark mode
- Location: e2e/p01-acquisition.spec.ts:74:1

# Error details

```
Test timeout of 30000ms exceeded.
```

```
Error: locator.click: Test timeout of 30000ms exceeded.
Call log:
  - waiting for getByRole('toolbar').getByRole('button', { name: '收起属性面板', exact: true })

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
      - generic [ref=e11]: SAR / InSAR 处理工作台
      - button "24 CPU" [ref=e12] [cursor=pointer]:
        - generic [aria-hidden] [ref=e13]: memory
      - button "下载" [ref=e15] [cursor=pointer]:
        - generic [ref=e16]:
          - img [aria-hidden] [ref=e17]: download
          - generic [ref=e18]: 下载
      - button "检索" [ref=e19] [cursor=pointer]:
        - generic [ref=e20]:
          - img [aria-hidden] [ref=e21]: travel_explore
          - generic [ref=e22]: 检索
      - button "Change language" [ref=e23] [cursor=pointer]:
        - img [aria-hidden] [ref=e25]: translate
      - button "Toggle theme" [ref=e26] [cursor=pointer]:
        - img [aria-hidden] [ref=e28]: light_mode
      - generic [ref=e29]:
        - status [ref=e30]: 后台运行中
        - button "退出应用" [ref=e32] [cursor=pointer]:
          - generic [ref=e33]:
            - img [aria-hidden] [ref=e34]: power_settings_new
            - generic [ref=e35]: 退出应用
  - main [ref=e37]:
    - generic [ref=e38]:
      - complementary [ref=e40]:
        - generic [ref=e41]:
          - generic [ref=e42]: 工程浏览器
          - button "首页" [ref=e43] [cursor=pointer]:
            - img [aria-hidden] [ref=e45]: home
        - generic [ref=e46]:
          - generic [aria-hidden] [ref=e47]: folder_open
          - paragraph [ref=e48]: 打开工程以查看数据和处理历史。
          - button "新建工程" [ref=e49] [cursor=pointer]
        - generic [ref=e52]:
          - button "下载任务" [ref=e53] [cursor=pointer]:
            - generic [ref=e54]:
              - img [aria-hidden] [ref=e55]: download
              - generic [ref=e56]: 下载任务
          - button "文件视图" [disabled] [ref=e57]:
            - generic [ref=e58]:
              - img [aria-hidden] [ref=e59]: folder
              - generic [ref=e60]: 文件视图
          - button "数据仓库" [ref=e61] [cursor=pointer]:
            - generic [ref=e62]:
              - img [aria-hidden] [ref=e63]: inventory_2
              - generic [ref=e64]: 数据仓库
      - separator "调整工程栏宽度" [ref=e65]
      - generic [ref=e69]:
        - main [ref=e71]:
          - tablist "工作流程页面" [ref=e72]:
            - generic [ref=e73]:
              - tab "1 检索与下载" [selected] [ref=e74] [cursor=pointer]
              - tab "2 数据与准备" [disabled] [ref=e78]
              - tab "3 参数与生成" [disabled] [ref=e82]
              - tab "4 运行" [disabled] [ref=e86]
              - tab "5 成果与 QC" [disabled] [ref=e90]
          - navigation "页内视图" [ref=e94]:
            - button "检索" [ref=e95] [cursor=pointer]
            - button "下载任务" [ref=e98] [cursor=pointer]
          - generic [ref=e102]:
            - generic [ref=e103]:
              - generic [ref=e104]:
                - generic [ref=e105]: SAR 数据检索
                - heading "为研究区域查找数据" [level=1] [ref=e106]
              - status [ref=e107]: ASF DAAC
            - generic [ref=e108]:
              - generic [ref=e109]:
                - heading "检索条件" [level=2] [ref=e110]
                - status [ref=e111]: Sentinel-1 · IW · SLC
                - generic [ref=e114] [cursor=pointer]:
                  - generic [ref=e115]:
                    - generic: 任务
                    - generic [ref=e116]:
                      - generic [ref=e117]: SENTINEL-1
                      - combobox "任务" [ref=e118]: SENTINEL-1
                  - generic [aria-hidden] [ref=e120]: arrow_drop_down
                - group "Sentinel-1 卫星 · 可多选" [ref=e121]:
                  - generic [ref=e123]:
                    - checkbox "SENTINEL-1A" [checked] [ref=e124] [cursor=pointer]:
                      - generic [ref=e129]: A
                    - checkbox "SENTINEL-1B" [checked] [ref=e130] [cursor=pointer]:
                      - generic [ref=e135]: B
                    - checkbox "SENTINEL-1C" [checked] [ref=e136] [cursor=pointer]:
                      - generic [ref=e141]: C
                    - checkbox "SENTINEL-1D" [checked] [ref=e142] [cursor=pointer]:
                      - generic [ref=e147]: D
                - generic [ref=e148]:
                  - generic [ref=e152]:
                    - generic: 开始日期 · UTC
                    - textbox "开始日期 · UTC" [ref=e153]: 2026-06-08
                  - generic [ref=e157]:
                    - generic: 结束日期 · UTC
                    - textbox "结束日期 · UTC" [ref=e158]: 2026-09-06
                - generic [ref=e161] [cursor=pointer]:
                  - generic [ref=e162]:
                    - generic: AOI 格式
                    - generic [ref=e163]:
                      - generic [ref=e164]: BBOX
                      - combobox "AOI 格式" [ref=e165]: BBOX
                  - generic [aria-hidden] [ref=e167]: arrow_drop_down
                - generic [ref=e171]:
                  - generic: 西、南、东、北
                  - textbox "西、南、东、北" [ref=e172]: 100,30,102,32
                - button "在地图上预览 AOI" [ref=e173] [cursor=pointer]:
                  - generic [ref=e174]:
                    - img [aria-hidden] [ref=e175]: center_focus_strong
                    - generic [ref=e176]: 在地图上预览 AOI
                - generic [ref=e179] [cursor=pointer]:
                  - generic [ref=e180]:
                    - generic: 轨道方向 · 可选
                    - combobox "轨道方向 · 可选" [ref=e182]
                  - generic [aria-hidden] [ref=e184]: arrow_drop_down
                - generic [ref=e188]:
                  - generic: 相对轨道 · 可选
                  - spinbutton "相对轨道 · 可选" [ref=e189]
                - generic [ref=e192] [cursor=pointer]:
                  - generic [ref=e193]:
                    - generic: 极化 · 可选
                    - combobox "极化 · 可选" [ref=e195]
                  - generic [aria-hidden] [ref=e197]: arrow_drop_down
                - generic [ref=e198]:
                  - button "检索 SAR 数据" [ref=e199] [cursor=pointer]:
                    - generic [ref=e200]:
                      - img [aria-hidden] [ref=e201]: search
                      - generic [ref=e202]: 检索 SAR 数据
                  - button "重置筛选" [ref=e203] [cursor=pointer]
              - generic [ref=e206]:
                - generic [ref=e207]:
                  - generic [ref=e208]:
                    - button "框选 AOI" [ref=e209] [cursor=pointer]
                    - button "定位覆盖范围" [ref=e212] [cursor=pointer]
                  - button "重试底图" [ref=e215] [cursor=pointer]
                  - generic [ref=e218]:
                    - generic:
                      - generic:
                        - img:
                          - generic:
                            - generic [ref=e219] [cursor=pointer]
                            - generic [ref=e220] [cursor=pointer]
                    - generic:
                      - generic [ref=e221]:
                        - button "Zoom in" [ref=e222] [cursor=pointer]: +
                        - button "Zoom out" [ref=e223] [cursor=pointer]: −
                      - generic [ref=e224]:
                        - link "Leaflet" [ref=e225] [cursor=pointer]:
                          - /url: https://leafletjs.com
                        - text: "| Tiles © Esri"
                  - generic: 底图加载失败
                - button "下载环境待配置" [ref=e231] [cursor=pointer]:
                  - generic [aria-hidden] [ref=e232]: info_outline
                  - generic [aria-hidden] [ref=e234]: expand_more
            - generic [ref=e235]:
              - generic [ref=e236]:
                - heading "检索结果 · 1" [level=2] [ref=e237]
                - generic [ref=e238]: SENTINEL-1 · 2026-06-08 — 2026-09-06
              - generic [ref=e239]:
                - button "全选已加载结果" [ref=e240] [cursor=pointer]
                - button "取消全选" [ref=e243] [cursor=pointer]
                - generic [ref=e246]: 0 项已选择 · 0.00 GiB
              - generic [ref=e247]:
                - table [ref=e249]:
                  - rowgroup [ref=e250]:
                    - row [ref=e251]:
                      - columnheader "Select all rows" [ref=e252]:
                        - checkbox "Select all rows" [ref=e253] [cursor=pointer]
                      - columnheader "卫星" [ref=e258] [cursor=pointer]:
                        - text: 卫星
                        - generic [aria-hidden] [ref=e259]: arrow_upward
                      - columnheader "成像时间（UTC）" [ref=e260] [cursor=pointer]:
                        - text: 成像时间（UTC）
                        - generic [aria-hidden] [ref=e261]: arrow_upward
                      - columnheader "相对轨道" [ref=e262] [cursor=pointer]:
                        - text: 相对轨道
                        - generic [aria-hidden] [ref=e263]: arrow_upward
                      - columnheader "轨道方向" [ref=e264]
                      - columnheader "极化" [ref=e265]
                      - columnheader "GiB" [ref=e266]
                      - columnheader "产品 ID" [ref=e267]
                  - rowgroup [ref=e268]:
                    - row [ref=e269] [cursor=pointer]:
                      - cell [ref=e270]:
                        - checkbox "Select row" [ref=e271]
                      - cell "SENTINEL-1D" [ref=e276]
                      - cell "2026-01-02T12:00:00Z" [ref=e277]
                      - cell [ref=e278]
                      - cell [ref=e279]
                      - cell "VV" [ref=e280]
                      - cell "0.00" [ref=e281]
                      - cell "S1D-first" [ref=e282]
                - generic [ref=e283]:
                  - generic [ref=e284]:
                    - generic [ref=e285]: "Records per page:"
                    - generic [ref=e288] [cursor=pointer]:
                      - generic [ref=e290]:
                        - generic [ref=e291]: "10"
                        - combobox "Records per page:" [ref=e292]: "10"
                      - generic [aria-hidden] [ref=e294]: arrow_drop_down
                  - generic [ref=e295]: 1–1 of 1
              - generic [ref=e297]:
                - button "已选清单 (0)" [ref=e298] [cursor=pointer]
                - button "仅下载" [disabled] [ref=e301]:
                  - generic [ref=e302]:
                    - img [aria-hidden] [ref=e303]: download
                    - generic [ref=e304]: 仅下载
                - button "从所选数据创建工程" [disabled] [ref=e305]
            - button "Expand \"网络设置\"" [ref=e310] [cursor=pointer]:
              - generic [ref=e311]: 网络设置
              - generic [aria-hidden] [ref=e314]: keyboard_arrow_down
        - separator "Resize" [ref=e315]
        - complementary [ref=e318]:
          - generic [ref=e319]:
            - generic [ref=e320]: 属性面板
            - button "收起属性面板" [expanded] [ref=e321] [cursor=pointer]:
              - img [aria-hidden] [ref=e323]: chevron_right
          - heading "对象详情" [level=3] [ref=e324]
          - tablist [ref=e325]:
            - generic [ref=e326]:
              - tab "属性" [selected] [ref=e327] [cursor=pointer]
              - tab "QC" [ref=e331] [cursor=pointer]
              - tab "历史" [ref=e335] [cursor=pointer]
          - generic [ref=e339]:
            - generic [aria-hidden] [ref=e340]: touch_app
            - paragraph [ref=e341]: 选择步骤、运行或成果，查看属性与来源。
  - contentinfo [ref=e342]:
    - generic [ref=e343]:
      - generic [ref=e345]: 本机引擎
      - separator [ref=e346]
      - generic [ref=e347]: 0 个处理任务
      - button "任务" [ref=e348] [cursor=pointer]
      - button "下载任务" [ref=e351] [cursor=pointer]:
        - generic [ref=e352]:
          - img [aria-hidden] [ref=e353]: download
          - generic [ref=e354]: 下载任务
      - generic [ref=e355]: Unassigned
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
  13 |  await page.getByLabel('West, south, east, north',{exact:true}).fill('100,30,102,32')
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
> 77 |  await page.getByRole('toolbar').getByRole('button',{name:'收起属性面板',exact:true}).click()
     |                                                                                 ^ Error: locator.click: Test timeout of 30000ms exceeded.
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