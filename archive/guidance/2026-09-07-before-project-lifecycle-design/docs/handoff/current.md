# 当前工作交接

[统一索引](index.md) · [提示词](prompts.md)

更新时间：2026-09-06。最新任务为[工程文件二进制封装](records/2026-09-06-project-binary.md)，新建/保存不再写明文配置，旧工程兼容读取；定向检查完成。前一实现任务：**P01 与公共外壳布局修正已完成定向测试，P01 整体验收继续保留原待办**。
最新接续入口：[地图与面板交互修正](records/2026-09-06-p01-map-panel.md)：地图不固定比例，高度独立于宽度；筛选常驻并删除收起功能，属性面板通过右边缘窄条展开。此前五主入口、左栏调宽/横滚、环境折叠和底图状态恢复保持。
前阶段：[实现记录](records/2026-09-06-p01-implementation.md)与[P01 卡](pages/p01-search-download.md)。不自动推进 P02。

## 已确定

Web 唯一、Sentinel 优先、工程固定 Profile、五页职责与 D01 科学未决项保持不变。
本轮用户明确授权完整实现 P01；随后要求产品界面删去研发过程与过多预先解释。
EOF 默认开，DEM 默认关；DEM 使用全部选中 SLC 的完整 IW/frame 联合范围，至少外扩 20 km。
1C/1D 的公共 EOF 已通过本机 ISCE2 选取、读取与插值；不同卫星不按月份互相替代。

## 本轮交付

- ABCD/IW/SLC 筛选与 UTC 校验，AOI 保留孔洞并拒绝不明 CRS/多几何隐式降级。
- 跨查询选择、身份恢复、独立查看、纯影像地图、底图重试、统一预览与三种获取入口。
- 可选 EOF/DEM、整景 DEM 元数据复核、Range 身份、有限并发、校验后发布、历史与补充获取。
- Python 定向测试 102 项、前端单元测试 13 项、Linux Firefox/Chromium 14 项和 Windows Edge→WSL 7 项通过。
- 真实 aria2 使用本地 HTTP/SAFE fixture 完成传输与复用；真实 ASF 整景认证下载和带宽饱和未验证。
- 真实服务和测试服务的最终状态、静态检查及文档验证见本轮记录。

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
本轮起始及发布前 launcher --status 都为 RUNNING，下载/处理任务/worker 均为 0；最终发布和清理结果见[实现记录](records/2026-09-06-p01-implementation.md)。这只是瞬时事实，后续仍需重查。
任务开始前如需使用服务，先用 launcher --status 检查；不要打印 session token、凭据或代理秘密。
记录自己启动的测试进程、端口与清理结果，不能把用户服务当测试服务停止。

## 当前交接结果

index、P01/P02 卡、current、migration 与两份 P01 设计已接续[本轮实现记录](records/2026-09-06-p01-implementation.md)。
原指导 7 份先归档到 archive/guidance/2026-09-06-before-p01-implementation/，包含摘要清单。
旧记录与原有未提交修改保留。未改变科学参数或用户科学输入。

最新服务核对（本次地图加宽任务）：用户服务 STOPPED，无活跃 worker/任务；未启动用户服务。独立 8767 浏览器 fixture 已清理。不可沿用前次 RUNNING 报告。

最新公共工程入口：命名 .pilot 新建、文件打开/识别、最近工程与旧工程导入已接线，详见最新实施记录。用户服务本轮核对仍为 STOPPED；独立测试 fixture 已清理，未创建用户计算/下载任务。

## 最新任务：CDSE 探测

[探测记录](records/2026-09-06-p01-cdse-probe.md)：目录可达，下载需认证，未测得 SLC 传输速度。下一步为官方登录后的有限传输对照；没有替换下载源。本轮结束核对用户服务 RUNNING，下载/处理/worker 均为 0，未创建后台传输。
