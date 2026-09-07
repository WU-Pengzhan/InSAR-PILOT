# P01｜检索与下载｜实现与定向验收

日期：2026-09-06。
本次用户指令与范围：授权完整实现 P01，核实 Sentinel-1C/D，支持 ABCD，可选 EOF/整景 DEM，完善下载可靠性与界面；随后要求减少产品解释文字，并核对 EOF 与 ISCE 的实际兼容性。
阶段：实现、修复、定向验收；页面状态为待验收。
页面任务卡：[P01](../pages/p01-search-download.md)。
上一份记录：[EOF/DEM 与网络设计](2026-09-06-p01-dem-network-design.md)，保持不变。

## 接受的决定与仍未知的事项

- 本轮明确实现授权覆盖早先设计阶段限制，不另设批准轮次。只做 P01，不实施 P02—P05。
- EOF 默认开、DEM 默认关；COP30 使用全部选中 SLC 的完整 IW/frame 联合范围，至少 20 km 外扩，可增至 200 km。
- 产品保留操作、进度和必要提示；研发过程、验证边界写入交接，详细下载诊断折叠展示。
- 文件生成月份、轨道有效期、卫星身份分别核对。卫星接替关系不能证明轨道状态向量可以互换。
- D01 phase stack、looks、滤波与参考约定未决定；本轮不改科学算法、参数或用户科学输入。

## 实际完成

### 产品与接口

- ABCD 多选、IW/SLC、UTC 全天、日期/轨道/平台验证；保留 NISAR/All 分组。
- BBOX/WKT/KML/Shapefile AOI；保留孔洞，拒绝多几何隐式缩小/包围盒替代及不明 CRS。
- 纯影像 Leaflet 地图、底图失败重试、重叠候选、独立查看、框选与 Escape 取消。
- 复合场景身份、跨查询/分页选择、按工程/全局恢复、失效身份核对、查询版本与取消保护。
- 仅下载、新建工程、添加工程统一获取预览；保存选择与开始下载分开。
- 可选 EOF/DEM、预览文件角色/路径/空间、下载历史筛选、暂停/继续/取消/重试、补充获取。
- 注册所需 Quasar 组件/指令，修复对话框标题和地图布局，精简产品文案。

新接口均在 /api/v1/data 下：

| 接口 | 合同 |
|---|---|
| acquisition-preview | 冻结场景、角色、工程 revision、查询来源、网络与 DEM 计划 |
| acquisition-commit | 同键同内容幂等、跨 Profile/revision 拒绝、保存选择/开始下载 |
| resolve-selection | 恢复后核对身份，明确可用/失效 |
| download-network | 直连/系统/手动代理、均衡/稳定、影像限速 |
| download-runtime/readiness | aria2、GDAL 与已配置账户状态；不声称认证已经验证 |

旧 downloads/selection API 保留。工程创建初始意图与工程记录一起写入；提交步骤持久化，
同工程相同活动集合与选项复用批次。不同工程保留独立尝试，经场景锁共享一次实际传输与已校验文件，
不合并各工程的取消权限。继续/重试仍创建关联新尝试，终态不原地重跑。

### 下载与数据合同

- SLC：已存在及新下载文件均检查内容；大小、SAFE 身份/成员、ZIP 全成员 CRC、TIFF 头、本地 SHA-256。
  本地摘要明确不是提供方签名/摘要验证。坏文件隔离，不再把非空文件直接视为完成。
- EOF：ABCD 显式识别，卫星/POEORB/完整成像时段/XML/OSV 顺序与覆盖核对；
  精密轨道未发布返回 unavailable，不静默替换成恢复轨道或另一卫星。
- 校验记录放 .integrity，坏文件放 .invalid，EOF 中间文件放 .partial。
  实测发现 ISCE2 的 OPOD* 通配会匹配同名前缀 JSON，已通过隔离目录消除。
- DEM：先预览目录 footprint；SLC 完成后读取全部 IW1/IW2/IW3 geolocation，
  多景联合后保守 WGS84 外扩并向外对齐。禁止按处理 AOI/burst 缩小。
- 新范围超过预览瓦片集合时要求重新预览；重新预览可使用已下载完整几何。
  保留 64 瓦片容量界限、反经线/极区明确拒绝；不静默截断。
- COP30：缓存/分片、ETag/区间/总长度核对，GDAL 拼接可取消；输出检查 CRS/范围、可读性、有限值与 nodata。
  缺片不填造成功，EGM2008 原始高程参考与未转换事实传给 P02。
- aria2 保留 TLS 校验、私有输入/凭据文件；日志与公共计划去除认证/签名下载引用。
  续传要求匹配可信 ETag、源身份和大小；身份不明保留旧 partial 并重新获取。
  无可信 ETag 时 SLC 使用单连接。
- 所有批次共享两个传输槽，均衡每个 SLC 四连接，稳定模式批内单景/两连接；
  DEM 每瓦片两段。影像限速独立于小型 EOF/DEM 请求。错误重试有退避。
  进度读取传输量，不把稀疏分片文件长度冒充已收字节。
- 发布资产保存 product_key、role、plan/attempt、integrity；共享 EOF 保存多景 product_keys。
  工程本地资产保留获取元数据，remote 引用解析形成新 revision。

### 真实目录与 ISCE 核查

证据均在 artifacts/p01-implementation-2026-09-06/：

- ASF 公开查询已发现 C、D 的 2026-09-05 IW SLC；B 有 2021-12-23 历史样例。
  A 在所查 2026-08—09 窗口无结果，不限日期样例最新为 2026-06-29。
  这是所查目录事实，不推断完整任务生命周期。
- asf-platform-probe.json、A_latest.txt 保存查询证据。安装的 ASF 依赖显式支持 ABCD。
- real-eof-probe.json：实际下载公开 S1C、S1D EOF，分别约 4.64 MB、4.63 MB，
  核对 XML mission、有效期和状态向量。
- isce-eof-probe.json：本机 ISCE2 分别自动选中正确 C/D 文件，读取 15 个邻近状态向量并完成 Hermite 插值。
  使用合成短成像时段测试读取，不是整景 SAR 处理或科学精度证明。
- august-orbit-catalog.json：公开 ASF 桶中，生成月份 202608 的 S1A 精密轨道前缀未返回条目；
  S1D 返回独立文件，生成于 8 月 1 日、有效期为 7 月 11—13 日。生成时间与有效期不可混为一谈。
- ISCE2 显式文件解析可读不等于对应卫星正确；当前实现先核对来源、XML 与卫星身份。
  没有证据支持把写作 S1A 的 EOF 按月份改作 S1D 使用。

来源：
[ASF Search API](https://api.daac.asf.alaska.edu/services/search/param)、
[ASF 公共轨道桶](https://s1-orbits.s3.amazonaws.com)、
本机 ISCE2 的 isceobj/Sensor/TOPS/Sentinel1.py。
未改本机 ISCE2；其现有代码已识别 C/D。

## 验证与证据

| 验证 | 本轮结果 |
|---|---|
| Web Python 定向后端测试 | 102 passed，5 条依赖弃用提示；无测试失败 |
| Ruff | 14 份修改 Python 源文件与 4 份测试通过 |
| mypy | 14 份修改源文件通过；follow-imports=silent、ignore-missing-imports |
| npm test | 5 文件、13 passed |
| npm run build | vue-tsc 与 Vite 通过，静态包已更新 |
| Linux Playwright | Firefox 7 + Chromium 7，共 14 passed |
| Windows→WSL | 原生 Windows Edge 共 7 passed |
| 真实传输进程 | 本地临时 HTTP + 合成 SAFE fixture，经真实 aria2 下载、隔离坏 ZIP、校验并复用通过 |
| 实际外部数据 | C/D 公共 EOF 与本机 ISCE2 读取/选取/插值通过 |
| 文档与差异 | 最终严格构建/链接/摘要与 diff 检查结果见本记录末尾 |

后端命令：Web Python -m pytest，下列文件一起执行 -q --tb=short：

test_p01_acquisition.py、test_p01_transport.py、test_web_explorer.py、test_web_download_controls.py、
test_asf_sentinel_adapter.py、test_cop30_dem_service.py、test_engine_store.py、test_engine_api.py、
test_engine_jobs.py、test_engine_recovery.py、test_engine_asset_closure.py、test_web_file_browser.py、
test_search_application.py、test_search_domain.py。

前端定向文件：e2e/explorer.spec.ts、downloads.spec.ts、p01-acquisition.spec.ts；
Linux 使用 Web Python fixture 服务和缓存浏览器，Windows 使用 Edge 连接同一隔离 WSL fixture 服务。
最终截图保存在 frontend/test-results-linux-final/ 和 frontend/test-results-windows-final/；
本轮保存副本到证据目录。检查了中英、明暗、1366×768、长路径/状态、空/失败、键盘、失效底图、
选择保留/乱序、四种选项和控制历史。对话框与地图截图已人工查看。

A01—A15、A17—A24 的相关基础分支有上述定向证据；不将其等同完整验收矩阵全部通过。
未执行真实 ASF 多 GB 整景账号下载、长时断网续传/认证失效、带宽饱和基准、
1000 景规模压力、原生 125%/150% 缩放全组合、全面故障注入或 SAR 数值处理。
此前 24 MiB 公共 Range 测速仅作网络方案依据；不承诺本轮已经跑满用户带宽。

## 服务与任务

- 本轮科学输入目录未修改；未启动用户 SLC/DEM 批量下载或科学 worker。
- 独立 fixture 服务端口 8767；最后服务 PID 125845 已正常关闭。
  Playwright 自管的前几次服务均随测试退出。真实 aria2 fixture 的临时 HTTP 线程与进程已退出。
- 用户 launcher 使用 /tmp/insar-pilot-browser-state。
  发布前重新核对为 RUNNING、下载/处理任务/worker 均为 0；
  通过支持的 --stop 空闲退出后重新启动，使新版静态包与 API 同时生效。
- 发布后 launcher --status：RUNNING，0 download jobs、0 processing jobs、0 worker processes。
- live-api-smoke.json：新版运行服务报告 ABCD 均支持、aria2/账户配置/GDAL 可用、DEM 获取接口已接线。
  不把账户“已配置”记作真实认证已验证。未记录 token/用户名/密码。
- service-final.json 保存重启结果与状态；已打开新版应用入口。

## 下一步

- 先读 AGENTS、index/current、P01 卡及本记录；产品实现无需重新征求授权。
- P01 下一阶段为真实账号整景/长时网络验收，保留本轮 fixture 与实际数据证据的区分。
- P02 仍待设计，只同步上游资产/DEM/轨道合同；不自动实施下一页或决定 D01。
- 已更新 index、current、P01/P02 卡、migration 与两份 P01 设计。
- 更新前 7 份指导归档于 archive/guidance/2026-09-06-before-p01-implementation/，有 SHA-256 清单。
  实现前 365 份源/测试/配置快照保留在证据目录 before/；原有未提交修改未清理。

## 最终文档检查

Web Python 执行 MkDocs build --strict 通过（退出 0）；8 份交接/设计文档共 70 条本地链接有效，7 份指导归档摘要一致，git diff --check 通过。结果见 artifacts/p01-implementation-2026-09-06/verification.json。

