# 公共外壳｜运行环境状态与失败提示
日期：2026-09-07。阶段：实现与定向验收。
用户指令：软件直接显示当前环境能否运行，不能则提示；环境由用户决定，不区分 Conda。
任务卡：[公共入口](../pages/shell-project-entry.md)。上一份：[环境合同核对](2026-09-07-runtime-compatibility-contract.md)，原样保留。

## 接受的决定与范围
- 最新用户指令取代软件负责安装/修复及 Conda 分类方案；仅检测和解释。未开发安装器。
- 共享运行环境页覆盖两种处理器基础依赖，不推进 NISAR 科学页面或 P02—P05。
- 环境就绪是 CPU 基础组件检查，不替代科学输入、输出、数值或 CUDA 验收。

## 实际完成
- 新增 application/runtime_check.py，使用与现有 Job 相同的 runtime_environment 和选定 Python 执行只读 probe。
- ISCE2 导入、TOPS 两个官方入口 -h、GDAL/PROJ；ISCE3/nisar.workflows.insar 导入、GDAL HDF5 两驱动/PROJ。返回状态、具体检查、解释器和时间。
- 缺解释器/模块/工具显示不可运行；超时/无效输出显示未确认；隐藏原生错误输出，避免泄露环境秘密。
- POST /api/v1/compute/check 新接口；硬件 /compute 不再无条件宣称 CPU 科学模式可用。OpenAPI 和 TS 模式已更新。
- ComputePanel.vue 替换原 JSON 和无条件可用提示；顶部入口改名“运行环境”，无工程也可打开。中英文本、两种主题、路径选择、重测、保存检测路径、失败提示和检测时间已接线。
- 每次打开重新检测；当前 Pipeline 的 Python 优先，其次最近保存的对应检测路径，空白明确使用应用环境。profiles 读取按 rowid 保持保存顺序。
- 修改路径清除旧状态；离开页面不接收旧结果。检测不持续轮询。保存检测路径不会修改旧 Pipeline。
- 当前 runtime-support.md 重写为用户管理环境、软件检测合同；README/安装说明/overview/migration/交接入口已接续。八份原指导先归档并保存 SHA256。

## 验证与边界
- Web Python pytest：test_runtime_check.py、test_engine_api.py、test_web_lifecycle.py 共 14 passed；覆盖缺失解释器、真实 Web 环境缺失处理器、逐项失败阻断 READY、超时/坏输出、认证与未检测硬件状态。
- Ruff 与适用 mypy（两个源码文件）通过；TypeScript 类型检查、Vite 构建通过；Vitest 16 passed。
- Windows Edge→WSL 两个定向浏览器用例通过，覆盖中暗 1366×768、英亮 1440×900、状态、编辑清除、HTTP 失败与恢复、无页面横向溢出。截图目视检查通过。
- 浏览器用例使用 mock 检测结果；真实本机 probe 单独保存 artifacts/runtime-check-2026-09-07/local-runtime-check.json：ISCE2 2.6.5 + GDAL 3.10.3、ISCE3 0.25.17 + GDAL 3.13.3，基础检查均 READY。
- 未执行科学处理/黄金数据比较或 CUDA；没有新增统一运行前门禁，没有重新验证 Linux Firefox/Chromium、原生缩放或非标准安装布局。此前临时 Linux 浏览器缓存已不存在。
- 原 Windows 构建因缺 Rollup 平台依赖失败；没有删除锁文件/node_modules。重新取得官方 Node 22.14.0 Linux 包并核对 SHA256，安装到持久 dev-tools 目录后 Linux 构建通过。只属于开发工具，不是软件用户运行依赖。
- MkDocs strict、新记录链接、8 份归档 SHA256 与 git diff --check 均通过。

## 服务与任务
- 本轮独立 8767 fixture：PID 9942 / tests/web_browser_server.py；浏览器结束后核对身份并 SIGTERM，最终确认退出。
- 未创建用户下载、科学 Run 或 worker；只读 probe 子进程已退出。
- 用户服务重启前 RUNNING，0 下载/处理/worker；为载入新 API 已正常停止并重启至 8765，默认浏览器会话已打开；真实新 API 再检 ISCE2 READY。最终 --status 仍为 RUNNING，0 下载/处理/worker。

## 下一步
- 用户从顶部“运行环境”查看当前检测；如需另一处理环境，自行选择对应 Python 并重测。不要求选择安装方式。
- 现有科学执行/路径适配仍保持原代码；页面结果说明当前配置在本程序执行环境中的基础可用性，不作任意系统安装保证。
- 后续按用户单页指令继续；P02/D01 原范围保持。不要重新启动已取消的安装向导方案。
