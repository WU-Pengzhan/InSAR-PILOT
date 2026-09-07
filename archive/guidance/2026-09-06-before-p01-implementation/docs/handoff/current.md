# 当前工作交接

[统一索引](index.md) · [提示词](prompts.md)

更新时间：2026-09-06。当前任务：**P01 前版设计方向获认可；EOF/整景 DEM 与网络补充已保存，设计待评审**。
本次完成已提出方案的文档落盘与交接，不是产品实现。下一项从 [P01 设计](../architecture/p01-search-download.md)和[本次记录](records/2026-09-06-p01-dem-network-design.md)接续；不自动推进 P02。

## 已确定

Web 是唯一开发界面，Sentinel first、NISAR later，一个工程固定一个 sensor Profile。
五页顺序与职责已同意；第三页采用参数/生成预览子视图，第五页组织成果/QC，逐步基础检查在第四页可见。
Recipe 不与页面一一对应。UI 不执行处理器、不从日志/目录猜科学成功。

本轮仅新增设计和更新交接/导航，未改产品代码、启动入口、Qt 依赖、科学参数或真实数据。
用户已明确 P01 首版聚焦 IW SLC，已选清单跨次检索保留；最新要求增加统一 EOF/DEM 勾选和整景 DEM 联合覆盖；补充稿建议 20 km 余量，并评估网络可靠性/速度。phase stack 具体产品仍为 [D01](index.md)，不由 P01 决定。

## 当前可复用实现

已有 Vue/Quasar 外壳、Leaflet 检索与 AOI、Sentinel ABCD、下载管理、
服务端路径选择、工程/计划/历史/基础成果与 QC、Inspector 和退出控制。
底层存在官方 ISCE2/ISCE3 适配与 SQLite/Job/Artifact 基础。
详细现状要以代码核对为准，旧预览功能不等于按五页完成验收。

关键共享入口：`frontend/src/App.vue`、`src/insar_pilot/web/api.py`、
`src/insar_pilot/domain/engine.py`、`src/insar_pilot/infrastructure/engine_store.py`。
每页具体起点见[任务索引](index.md)。

## 本机环境记录

以下在 2026-09-06 仅核对路径存在，未重新证明所有包/浏览器可运行；临时目录尤其需要任务启动时重查。

| 项目 | 本机位置/事实 |
|---|---|
| WSL 仓库 | `/home/griffin/projects/insar-pilot` |
| Windows 访问 | `\\wsl$\Ubuntu\home\griffin\projects\insar-pilot` |
| Web Python | `/home/griffin/.local/share/insar-pilot/web-venv/bin/python` |
| 原科学/后端测试 Python | `/home/griffin/miniconda3/envs/insar/bin/python` |
| 本机 Web launcher | `/home/griffin/.local/bin/insar-pilot-web` |
| 现有 Linux Node | `/tmp/node-v22.14.0-linux-x64/bin/node` |
| Playwright 浏览器缓存 | `/tmp/insar-pilot-playwright` |
| HEAD | `31ccf3afd23c2ea118dfe8bc99c0697bd5f505ec` |
| 工作树 | 有大量原有修改及未跟踪内容，不能 reset/clean；HEAD 不包含全部当前实现 |

开发命令在 WSL 仓库中执行。Windows PowerShell 下使用
`wsl -d Ubuntu --cd /home/griffin/projects/insar-pilot -- <command>`。
Linux 的 rg 在此前环境中不可用，可用 Windows rg 或其他只读搜索方式。

## 验证入口与限制

前端脚本已核对：`npm test`、`npm run build`（含类型检查）、`npm run test:e2e`。
相关测试文件在任务卡中列出。Python 新引擎/API 用 Web 环境，复用后端测试按依赖选择 insar 环境。
修改 Python 时运行 Ruff/适用 mypy；文档修改使用装有 MkDocs 的 Web 环境执行严格构建。
不把本机路径硬编码进产品配置，不把旧测试数当成本次执行结果。

浏览器验证使用独立 fixture 服务与临时数据；真实服务仅在必要且授权范围内操作。
本轮使用 launcher --status 只读探测，起始时服务 RUNNING，下载/处理任务/worker 均为 0；末次时间与结果见[本次记录](records/2026-09-06-p01-dem-network-design.md)。这只是瞬时事实，后续仍需重查，未操作用户服务。
任务开始前如需使用服务，先用 launcher --status 检查；不要打印 session token、凭据或代理秘密。
记录自己启动的测试进程、端口与清理结果，不能把用户服务当测试服务停止。

## 当前交接结果

[P01 设计](../architecture/p01-search-download.md)已保存；P01 卡、总索引、current、migration、架构入口与 MkDocs 导航同步，P02 卡仅增加上游依赖，P02—P05 仍待设计。
主设计包括 A01—A16；新增[EOF/DEM 与网络补充](../architecture/p01-ancillary-downloads.md)增加 A17—A24。两项本地探针确认 S1D EOF fallback 与非空坏 ZIP 跳过问题；24 MiB 公共 Range 测试仅为限量链路证据，不代表真实 ASF 性能。未做产品修复或 Web DEM 接线。

[本次设计交接记录](records/2026-09-06-p01-dem-network-design.md)记录验证、归档、服务与下一动作。
[原准备记录](records/2026-09-06-guidance-preparation.md)保持不变。产品代码、既有工作树修改、科学输入和黄金数据保留。
