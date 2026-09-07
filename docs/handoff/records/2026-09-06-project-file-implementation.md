# 公共外壳｜.pilot 工程入口实现
日期：2026-09-06。用户明确指令“开始更新代码”。
阶段：第一轮实现与定向验收。
[任务卡](../pages/shell-project-entry.md) · [当前合同](../../architecture/project-file-entry.md)。
上一份记录：[工程入口设计](2026-09-06-project-file-design.md)，原样保留。

## 接受的决定与仍未知的事项
- 实施已讨论的工程文件识别、新建、打开、最近工程及旧格式导入。
- 命名 .pilot 是工程入口，数据库/科学文件保留配套目录；单个描述文件不是完整备份。
- 搬迁/副本、系统双击关联、便携导出不属于本轮。P02 完整设计和 phase stack 科学未决项不变。

## 实际完成
- infrastructure/project_file.py：只读识别、单入口解析、名称合法性、schema/format/数据库 ID/待恢复修订校验。
- engine_store.py：实际 project_file 贯穿修订和恢复；兼容已有 project.pilot 与无 format 旧 Web 文件。
- application_state.py：重复打开复用，拒绝 ID/位置冲突；最近列表保留不可用项、入口位置、打开时间和原工程定义响应，读取不恢复 pending。
- web/api.py：typed inspect、creation-preview 与 parent_directory 创建参数；打开/导入重校验，不初始化缺失数据库。
- frontend/src/ProjectEntry.vue：新建名称/保存位置/传感器/路径预览，文件选择和校验摘要，旧格式导入表单，响应序号防过期选择。
- FilePicker/FilePathField：项目专用 .pilot 过滤，服务端分页前筛选，目录仍可浏览；项目文件图标。
- App.vue：新建/打开接线，最近文件位置/时间/状态；移除旧表单和失去入口的选择创建状态。
- application/acquisition.py 与 engine_data.py：检索创建/旧工程导入也生成命名文件；导入源敏感配置先校验，完成后登记。
- 同步 OpenAPI JSON 与生成 TypeScript 类型；内部 EngineStore.create 默认名仍兼容原 CLI/调用。
- 跨页只变更公共工程入口及创建结果位置，不改获取策略、Profile 科学含义或 Run/Artifact 历史。
- 已归档八份受影响指导文件至 archive/guidance/2026-09-06-before-project-file-implementation/，附 SHA-256 清单。

## 验证与证据
- Web Python 定向测试：test_project_file_entry、engine_store、engine_recovery、engine_api、web_file_browser、engine_jobs、p01_acquisition 共 75 passed。
- 随后补齐最近列表完整定义响应兼容，project_file_entry + engine_api 21 passed，不能与前轮合并为全量结果。
- Ruff 变更 Python 文件通过；Mypy 7 文件通过，使用已有 insar 环境的 mypy、Web Python 依赖路径、follow-imports=silent；仅关闭第三方无类型声明 import-untyped 报告。
- npm test 最终 6 文件、15 passed；App 测试旧 Project folder 断言随保存位置表单更新。
- npm run build：vue-tsc/Vite 通过，静态资源已更新；OpenAPI 类型重新生成。
- Linux 首轮 file-picker/project-entry/shell-layout 24 passed。
- 最后布局/入口验证：Linux file-picker + project-entry 16 passed；Windows 同两文件及 shell-layout 12 passed。
- 扩展 P01 获取回归最初暴露旧顶栏面板选择器和初始化等待问题；测试调整为面板自身按钮并等待初始化完成。最终 P01 3 项 Windows、6 项 Linux 通过；未修改 SAR 检索逻辑来迎合测试。
- 浏览器覆盖 .pilot 文件点击打开、命名新建/最近文件、不可读/缺数据库、旧工程导入、过期响应、输入引用多选、中文/明暗/长路径/窄视窗与 Windows/WSL 路径映射。
- artifacts/project-file-2026-09-06/ 保存截图/浏览器记录；新建路径预览截图已目视检查。
- fixture 旧工程与数据为测试生成，没有操作用户旧工程，没有真实科学运行或账号下载。
- 原生浏览器 125%/150% 完整矩阵、长时大规模工程列表压力、真实项目迁移和科学数值对照未执行。
- 本轮没有实现搬迁/重新定位 GUI、系统文件关联、备份导出或手工编辑导入 GUI。

- MkDocs strict、git diff --check、70 条相对文档链接及八份归档摘要检查通过。

## 服务与任务
- 本轮开始及检查时用户 launcher --status 为 STOPPED，无活跃 worker/任务；未启动/重启用户服务。
- Linux 自管 fixture PID 185346，随测试结束退出。
- 独立 fixture PID 188838、端口 8767 提供 Windows 与最终 Linux 检查；核验 cmdline 后 SIGTERM 清理。
- 没有本轮用户计算/下载任务；不记录 token/凭据。

## 下一步
- 下一位从本记录、任务卡、当前工程文件合同接续。
- 用户下次启动 Web 应用后使用新建/打开文件入口；已有 project.pilot 可直接选择。
- 后续搬迁/副本/导出/系统关联按独立指令，不自动推进 P02。
- index/current/公共任务卡/P02 依赖/project-model/storage/migration 已同步；历史设计记录保持。
