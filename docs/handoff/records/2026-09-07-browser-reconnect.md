# 公共外壳｜选择浏览器与关闭后重连
日期：2026-09-07。阶段：修复与定向验收。
用户指令：不希望只能打开默认浏览器，关闭之后重连失败；随后确认具体页面是“连接此浏览器／无有效本机会话”。
任务卡：[公共入口](../pages/shell-project-entry.md)。上一份：[运行环境状态](2026-09-07-runtime-status-ui.md)。

## 原因与范围
- 起始服务 RUNNING，无任务；用户确认的是会话失效，不是后台退出。
- 原 Cookie 无 Max-Age，关闭浏览器后不能保证保留；服务重启另会轮换 token；快速重启端口探测可因 TIME_WAIT 换到随机端口。后两项是代码核对发现的额外重连风险，不断言用户本次经历了全部情况。
- Web 产品方向保持；系统默认浏览器只是默认选择。未开发或恢复 Qt。

## 实际完成
- launch.py 支持 --browser default/firefox/chrome/edge；WSL 指定 Windows 浏览器，原生 Linux 指定本机浏览器；--no-browser 与选择项互斥，显式浏览器失败不静默改用默认。
- 凭据继续通过 stdin 传递给 Windows 打开辅助进程，不打印链接凭据。已有状态目录下安全随机凭据正常重启复用，service.json 保持 0600。
- API Cookie 改为 30 天、HttpOnly、SameSite=Strict；Host/Origin/HTTP/WebSocket 身份边界保留。无有效 Cookie 的新浏览器仍须首次连接，不开放匿名 API。
- 指定端口探测允许正常重启复用；冲突明确报错，不再静默选随机端口（显式 --port 0 除外）。
- 连接页说明首次/清理 Cookie/私密模式和指定浏览器；退出页明确停止后台后需要终端启动，不能靠刷新。
- README/生命周期规范/索引/current/公共卡/migration 同步，六份旧指导归档并保存摘要。

## 验证
- Web Python：test_web_launch.py、test_web_lifecycle.py、test_engine_api.py 17 passed；最终 Linux browser 查找回退补充后 test_web_launch.py 6 passed。
- 含真实独立服务停止/重启，验证相同端口、相同凭据及旧 Cookie 再连；跨 Origin 仍拒绝，指定浏览器派发通过模拟验证。
- Ruff、mypy 两源码文件、前端类型与构建通过，Vitest 16 passed。
- Windows Edge→WSL 11 项最终全通过。首次回归 10 passed/1 failed 是旧用例仍假定“查看任务”直达下载，已按现有后台任务页 → 下载入口更新验证；未改写产品导航。
- 额外使用真实持久浏览器用户目录：结束 Edge 进程后用同一目录启动，再打开裸地址且 sessionStorage 无 token，重连通过；相关 2 用例通过。首次使用 UNC 仓库中的浏览器 profile 未能恢复，换为 Windows 本地临时 profile 后通过；测试 finally 清理自建本地 profile，不修改用户浏览器数据。
- 浏览器证据 artifacts/browser-reconnect-2026-09-07/。Cookie 生命周期 30 天未做实际等待测试；Linux Firefox/Chromium 与 Windows Firefox/Chrome 的真实进程重开未实测。
- MkDocs strict、git diff --check、6 份归档摘要与新记录链接核验通过；本轮不执行科学计算或下载。

## 服务与任务
- 独立 fixture PID 28142 / tests/web_browser_server.py，8767；结束后按身份 SIGTERM，已确认 /proc/28142 不存在。
- 不触碰用户数据/Run/Artifact；自管 pytest 服务与测试浏览器在 finally 退出。
- 发布时先核对真实任务为空，再正常停止并 --no-browser 启动新版，避免再次强制弹出默认浏览器；最终地址 8765，RUNNING，0 下载/处理/worker；真实 API 返回 30 天 HttpOnly/Strict Cookie，未打印其内容。

## 下一步
- 用户可选择 --browser firefox/chrome/edge 连接一次；其后同一主机地址和浏览器可直接打开，后台须在运行。
- 不把清理 Cookie/私密窗口或软件明确退出当作自动重连承诺。后续科学页面仍按既定任务卡推进。
