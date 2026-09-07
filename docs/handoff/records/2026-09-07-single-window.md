# 公共外壳｜单窗口占用与自动接续
日期：2026-09-07。
本次用户指令与范围：任意浏览器直连同一地址；已有窗口使用时不能抢占，关闭后其他浏览器可连接。用户明确要求开始修改。
阶段：实现、修复与定向验收。
页面任务卡：[公共外壳](../pages/shell-project-entry.md)。
上一份记录：[直接访问端口](2026-09-07-direct-browser-access.md)，原样保留；直接访问能力继续，进入工作台新增单窗口约束。

## 接受的决定与仍未知的事项
- 每个本机服务同一时刻仅一个窗口/标签页进入；独立浏览器和同浏览器新标签都等待，无抢占操作。任意浏览器可以申请，不要求用户授权浏览器或管理 token。
- 关闭当前窗口释放使用权；异常断开以最后有效心跳后约 15 秒过期，自动重试可能再需数秒。后台下载/处理生命周期独立。
- 刷新释放旧文档，有多个等待者时先成功申请者进入；不保留某浏览器优先权。睡眠/冻结窗口恢复后需重新申请。后端已接受的操作允许完成，释放不等于回滚或取消。
- 本轮不改变五页划分、P01 科学获取合同或处理参数。既有 phase stack D01 未决，P02—P05 按后续单页指令开展。

## 实际完成
- 新增 `src/insar_pilot/web/window_lease.py`：单调时钟、15 秒有效期、临时随机持有者身份，旧身份不能续期或释放新持有者。
- `web/api.py` 新增同源会话保护的 `/api/v1/window` WebSocket，原子申请、服务端 ping/页面 pong、断开释放。浏览器业务 API、事件流、瓦片/预览检查占用，过期/缺失返回 423；写入锁内再次检查。
- `frontend/src/SingleWindow.vue` 作为根入口：占用成功后才挂载 App，否则显示中英/明暗占用页，每 2.5 秒重新检查。关闭、pagehide、连接丢失清理占用；后台明确退出保留既有“退出完成”显示。
- `window-session.ts` 的使用权只存页面内存；共享 Cookie 不共享使用权。`api.ts` 冻结每次请求的身份，认证补试不能改用新窗口身份；迟到的旧 423 不踢出新连接。App、SearchMap、MapWorkspace 原生图片/瓦片带临时使用权；事件订阅检查相同身份。
- CLI/service-control 以有效 Bearer 且无浏览器 Origin/Fetch Metadata 保留管理访问；浏览器会话/同源/Host 防护仍在。没有新增登录流程，不向日志、快照或交接写入使用权值。
- 8 份修改前指导原样归档至 `archive/guidance/2026-09-07-before-single-window/`，附 SHA-256 清单；README 中英、Run/Job、GUI、migration、索引、current、外壳卡更新（共 8 份文件）。历史记录未覆盖。

## 验证与证据
- Web Python：`pytest -q tests/test_window_lease.py tests/test_engine_api.py tests/test_web_lifecycle.py tests/test_web_launch.py` → **22 passed**。含共享 Cookie 不能抢占、旧身份/写入拒绝、真实 15.2 秒无响应超时、释放不改写模拟后台下载记录、会话和启动/退出回归。依赖发出 2 项弃用提醒，无失败。
- `ruff check` 改动的 2 个后端文件和 2 个 Python 测试文件通过；mypy 对 `api.py`、`window_lease.py` 通过（使用 Web Python 依赖路径）。
- Linux Node：Vitest **20 passed**，包括旧请求认证重试不借用新使用权、旧 423 不干扰新窗口、当前 423 不重复提交；Vue 类型检查和 Vite 构建通过。
- Windows Edge→WSL：`window-lease.spec.ts session.spec.ts reconnect.spec.ts lifecycle.spec.ts downloads.spec.ts` **17 passed**（名称匹配同时包括 project-lifecycle）。覆盖多标签、独立真实 Chrome 等待接续、Cookie/刷新、下载控制、工程创建/打开、明确退出/意外断开、中英和明暗页面。此前同轮 explorer/map/logo/面板与工程/占用子集 7 passed；不累加为全量套件。
- 证据：`artifacts/window-lease-2026-09-07/final-windows/`，包含已人工查看的 `occupied-zh-dark.png`，1366×768 未见裁切。下载/工程浏览器测试使用 8767 fixture 和临时目录，后台任务保持测试是模拟记录，没有启动真实 ASF 下载或 SAR 计算。
- 未实测本轮 Linux Firefox/Chromium、移动浏览器、OS 休眠/后台长期节流、多种缩放和长时间运行。当前 Windows Chrome/Edge 实测不替代全部平台验收。科学参数、黄金输入和已发布成果未改动。

## 服务与任务
- 接续核对时本机 launcher 报 STOPPED，无活跃应用 worker/任务。此前“仍运行”的记录为较早瞬时状态，不作为本轮事实。
- 确认无活动任务后用 `insar-pilot-web --no-browser --port 8765` 启动新版，状态仍使用 `~/.local/state/insar-pilot`，没有弹出默认浏览器。
- 本轮测试 fixture PID 67858、端口8767（`tests/web_browser_server.py`），结束核实进程命令后发 SIGTERM。最终清理与部署结果在下方补充。
- Playwright 仅关闭自己创建的页面/浏览器；不关闭用户窗口、不抢占；正式服务浏览器核对不创建工程或任务。

## 下一步
- 用户直接访问 http://127.0.0.1:8765/。占用时关闭原工作台窗口即可由等待页接续；异常断开等待超时。关闭窗口不取消任务，明确退出仍走空闲检查。
- 下一位先读当前 Run/Job 生命周期、此记录和索引；本次外壳修改结束，不自动推进 P02—P05 或环境安装。
- 如后续增加 API 调用/原生图片/事件通道，沿用 `api`、`windowUrl` 与后端占用守卫；不要在 Cookie/localStorage 共享使用权，不新增抢占按钮。
- 索引、current、公共卡与 migration 已更新；旧记录保持不可变。待用户决定只限原有 D01 等后续科学合同。


## 最终部署与清理核对
- 正式 8765 服务实测：独立 Edge 先进入、Chrome 显示占用，关闭 Edge 后 Chrome 自动进入；结果保存在 `artifacts/window-lease-2026-09-07/live-browsers.json`。首次部署检查的定位器匹配两个 splitter 导致测试脚本严格模式报错，改用 first 后通过；产品未因此修改。
- 所有部署检查浏览器已在 finally 关闭，不占用用户工作台。自管 fixture `/proc/67858` 已不存在，端口8767测试服务已清理。
- 最后 `insar-pilot-web --status`：RUNNING，0 download jobs、0 processing jobs、0 worker processes。用户可直接连接8765；此为本次瞬时检查，后续任务仍须重查。
- MkDocs strict 通过；GUI 内新增章节链接修正为文件链接后复查。8 份归档摘要、9 份改动文档的117条本地文件链接及 git diff --check 通过。构建输出位于 `/tmp/insar-pilot-single-window-docs`，没有常驻文档服务。
