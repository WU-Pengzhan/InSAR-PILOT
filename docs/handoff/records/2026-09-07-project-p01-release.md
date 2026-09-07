# 公共外壳 / P01｜工程、下载与界面收敛
日期：2026-09-07。
用户范围：实施工程轮廓和数据下载优化，研究产品案例、形成规范并落实产品界面。
阶段：实现与定向验收。
任务卡：[公共入口](../pages/shell-project-entry.md)、[P01](../pages/p01-search-download.md)。
上一份：[processing 简化](2026-09-07-processing-simplification.md)，原样保留。

## 接受的决定与范围
- 用户明确授权本轮代码/UI 工作；执行公共外壳与 P01、共用视觉，未扩展 P02—P05 科学内容。
- .pilot 二进制、五页、单工程 Profile、官方算法保持；phase stack D01 未决定。
- 简化 processing、过程记录默认隐藏、启动先选工程已实施。

## 实际完成
- ProjectLayout 布局 2：Web/检索创建与 legacy 导入采用 data、processing、products；records/runs/plans 在 .insar_pilot 中。旧工程布局 1 不移动，内部 create 默认 1 保持兼容。
- App.vue：不恢复 pilot-project，工程完整加载后才选中；关闭清理工程数据/计划/日志与订阅，过期请求隔离、事件刷新合并、最多显示 500 条。未打开仅 P01；辅助设置/后台状态可用。
- 首页显示三个操作、最近工程/路径/Profile/数据与任务摘要；新建预览父目录/最终路径，P01 新建也用父目录+名称。
- acquisition-preview 接收 new_project 并冻结目标，提交改目标拒绝；项目新数据在隐藏 transfers 校验后复制/hash/原子发布到 data/<role>/<sha256>，登记成功后清理已完成暂存大文件。
- 既有注册源核对 snapshot 后跨工程引用；单份应用 Job、来源身份锁、真实保存位置保留；重试新 ID，目标不改变。
- 下载记录服务端分页默认 10、上限 50，支持状态和文本筛选；活动 3 秒/空闲 15 秒轮询，旧响应丢弃，任务记录折叠，复用来源明确显示。
- 限速按本批次 worker 分配，单景/稳定模式不再固定除以二；不宣称全局动态带宽保证。
- 下载 worker/control 日志按尝试 ID 独立保存；现有 aggregate 日志保留、不覆盖历史。
- 复用 ASF/aria2/EOF/COP30/ISCE 科学能力；本轮无新 CDSE provider 或实际 SAR 处理。
- 阅读官方案例并形成 [UI/UX 规范 1.0](../../architecture/design-system.md)：系统字体、色彩/间距、组件与状态规则，落实全局样式、首页/P01/下载/工程入口。
- 15 份旧指导/MkDocs 文件按清单归档 archive/guidance/2026-09-07-before-project-p01-release/，不覆盖旧记录。

## 验证与证据
- 证据目录：artifacts/project-p01-final-2026-09-07/；资料抓取 design-sources.json。
- Python 12 个定向文件 108 passed；新增布局、历史隔离、冻结目标、发布/取消/改写拒绝、分页/隐藏目录、worker 跨项目复用。日志改动后 23 passed；最后工程详情路径响应与日志隔离补验 20 passed（重叠回归，不与 108 相加）。
- 真实 aria2 使用本机 HTTP/SAFE fixture；worker 编排测试使用明确的传输/元数据 fixture，不代表科学元数据或外部平台吞吐验证。
- 前端类型/Vite 构建通过；生成 OpenAPI 与 TypeScript 请求模式；最终 Vitest 6 文件 16 passed。
- Linux 初轮 30 passed/2 failed：旧测试尝试点击加载期间禁用的 P03，已调整为检查禁用与公共页不抢焦点。
- Linux 第二轮 30 passed/2 failed：旧测试假定属性默认展开，已调整为新默认收起；P01/下载复验 10 passed。其他 22 个场景已在第二轮通过；不把多轮简单累加为更多独立场景。
- Windows Edge→WSL 16 passed；截图目视检查英文首页、中文暗色下载页，主操作/路径/状态/控制无页面溢出。地图 fixture 使用占位瓦片，不证明真实底图联网。
- Ruff 改动源码/测试通过；mypy 10 个源码文件通过，最后 API/下载改动 2 文件再检通过。现有 mypy unused-section 提示和 Starlette 测试依赖弃用警告未影响通过。
- MkDocs strict 构建、git diff --check 通过；15 份归档 SHA256、160 条相对链接核验通过。
- 最终摘要：artifacts/project-p01-final-2026-09-07/final-validation.json。
- 1366×768、1440×900、中英/主题、长路径/错误/地图尺寸/五页/打开关闭/下载控制已纳入定向用例。真实原生 125%/150% 缩放、超大列表、完整无障碍审计未验收。
- 未执行真实 ASF 整景长时下载、CDSE 认证吞吐、SAR 计算或黄金数据对照。

## 服务与任务
- 起始/重启前用户服务 RUNNING，0 下载/处理/worker；本轮未创建用户数据任务。
- 自管 Linux/Windows fixture PID 224256、225995、227788、228474 全部确认退出。228474（8767）的 tests/web_browser_server.py 身份核对后 SIGTERM，其余随测试结束退出。
- 空闲用户服务已通过 launcher --stop 正常退出并启动新版。首次快速重启在端口暂不可绑定时选到 44048；确认 8765 可用后再次正常重启，最终地址恢复 http://127.0.0.1:8765/，launcher 已调用默认浏览器进行会话连接。
- 新下载分页接口在真实服务核对通过：2 条历史尝试、0 活跃下载；最终 launcher --status 的处理/worker 状态见完成检查，均为 0。
- 未取消/删除历史下载，未停止用户科学进程；session token 未输出或写入证据。

## 后续与保留项
- 本轮工程/P01 作为下一阶段基线；后续按用户指令进入 P02，沿用设计规范。
- 真实网络吞吐与长时认证/续传另行测量；CDSE 账号尚不进入产品。
- 手动复制既有数据、便携打包、整工程搬迁、系统双击关联未提供，不宣称复制单个 .pilot 可备份整个工程。
- 上游工程数据就绪不等于 P02 科学兼容/DEM 椭球高已验收。
- index/current/公共/P01/P02 卡与 architecture/migration/GUI/storage/data/工程/P01 规范均已接续；旧用户输入、日志与黄金数据保持。

## 复验入口与下一动作
- Web Python：`python -m pytest -q tests/test_project_layout_acquisition.py tests/test_engine_api.py tests/test_web_download_controls.py`（最终 20 passed）；日志改动后另一轮包含 test_web_explorer.py，共 23 passed。
- 前端：`node node_modules/vitest/vitest.mjs run`；`npm run build` 含 vue-tsc；Windows Playwright 使用独立 8767 fixture，对 project-lifecycle、project-entry、shell-layout、explorer、downloads、p01-acquisition 六份用例执行。
- 文档：Web Python `-m mkdocs build --strict --site-dir /tmp/insar-pilot-docs-project-p01-final-20260907`；归档/链接通过只读脚本逐项核对。
- 下一位从 handoff/index.md → current.md → P02 卡进入。先设计已注册 SLC/Orbit/DEM 的数据就绪视图和准备合同，按用户单页指令实施；不要把来源完整性当作全部科学兼容验收。
- 用户尚未决定的 D01：phase stack 是配准复数 SLC、缠绕干涉相位还是二者；在 P03/P05 科学合同冻结前明确，不阻碍先做 P02 页面设计。
