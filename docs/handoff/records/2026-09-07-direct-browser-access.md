# 公共外壳｜任意浏览器直接访问本机端口
日期：2026-09-07。阶段：实现与定向验收。
用户要求：后台端口运行时能直接访问并切换浏览器，不接受每个浏览器先经启动器授权。
任务卡：[公共入口](../pages/shell-project-entry.md)。上一份：[浏览器重连](2026-09-07-browser-reconnect.md)，原样保留，人工首次授权要求被本次取代。

## 接受的决定与实际完成
- 本机单用户模型下页面自动取得本机会话；用户无 token/登录/浏览器授权操作。未改为远程公开服务。
- POST /api/v1/session 仅接受同源 Origin、自定义 X-Pilot-Workbench 请求头及同源 Sec-Fetch-Site（旧浏览器无此头时由前两项约束）；响应仅 connected=true，凭据在 HttpOnly Cookie。
- TrustedHost/Origin 检查与 loopback 监听保持；无 CORS 授权，阻止外部来源/简单表单/预检建立会话；页面加 frame-ancestors none 和 X-Frame-Options DENY。
- api.ts 在业务请求确定返回 401 后合并自动建立会话，再重试该被拒绝请求一次；不重试 500 或模糊执行结果。旧 tab token/链接兼容。WebSocket 因会话问题关闭时可通过 HTTP 检查恢复。
- launcher 打开普通地址，不再生成 token fragment。--no-browser 后直接手动打开端口即可；--browser 只选打开的应用。
- 原人工连接页改为自动连接失败后的本地排查提示，不引导用户给浏览器授权。
- README/运行生命周期/任务索引/current/公共卡/migration 更新，修改前六份指导归档并保存摘要。

## 验证与证据
- 后端 test_engine_api.py、test_web_lifecycle.py、test_web_launch.py 18 passed：同源自动建立、外部 Origin/null Origin/错误 Host/跨站 Fetch/简单请求与预检拒绝，Cookie/iframe 边界，原任务/退出/重启行为。
- Vitest 18 passed；新增首次401后的建立与原请求重试、并发合并；原模糊失败不重试保持。Ruff、mypy 两文件、类型检查、Vite 构建通过；OpenAPI/TS 模式已再生成。
- Windows 浏览器测试 12 passed：Edge 新上下文直接访问、独立上下文切换、清 Cookie 后刷新、持久 profile 重开、旧 token 兼容、工程入口/任务/退出；额外真实 Chrome 新进程直接打开 localhost（无 token），并打开工程接收 WebSocket 事件。
- 使用独立 8767 fixture 与临时工程；证据 artifacts/direct-browser-2026-09-07/windows/。Chrome 为显式 PILOT_TEST_CHROME=1 可选安装检查。
- 本轮无 Linux Firefox/Chromium 或移动浏览器实测，无新科学计算/下载。已测 Edge/Chrome 使用标准 Cookie/JavaScript 能力；全局禁用 Cookie 时不承诺自动连接。
- MkDocs strict、git diff --check、6 份归档摘要和新记录链接检查通过。

## 服务与任务
- 起始真实服务运行、无活跃下载/处理/worker；未创建用户计算或下载。
- 自管 fixture PID 58100 / tests/web_browser_server.py，端口8767；测试结束后核实身份 SIGTERM，/proc/58100 已不存在。Playwright 独立浏览器/临时 profile 在 finally 退出清理。
- 发布正常重启真实后台，使用 --no-browser 不弹出默认浏览器；最终在 8765 运行，0 下载/处理/worker。真实部署使用全新 Edge/Chrome 上下文直接打开主页通过，未设置 token；见 live-browsers.json。

## 下一步
- 用户直接在任意浏览器打开 http://127.0.0.1:8765/ 即可，不要求新命令或手动授权。
- 后台确实退出后才需要启动；--browser 选择和30天Cookie为实现细节，不再作为访问前置条件。
- P02—P05 科学界面仍按页推进，当前任务不扩展安装/科学处理。
