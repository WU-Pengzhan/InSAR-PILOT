# 当前工作交接

当前入口行为：[单窗口占用与自动接续](records/2026-09-07-single-window.md)。任意浏览器直接打开本机端口，但同一时刻仅一个窗口/标签页进入工作台；其他页面等待，不抢占。关闭当前窗口后自动接续，异常断开约 15 秒失效，后台任务继续。

本次部署已在正式 8765 验证 Edge→Chrome 等待接续，检查浏览器与 8767 fixture 已关闭。最终状态为 RUNNING、0 下载/处理/worker；详见[最新交接](records/2026-09-07-single-window.md)，后续仍须重查。

历史重连修复（手动首次连接要求已被取代）：[浏览器选择与重连](records/2026-09-07-browser-reconnect.md)。本机会话保留 30 天，正常后台重启保持凭据/端口，可显式选择浏览器。

当前接续：[运行环境状态界面](records/2026-09-07-runtime-status-ui.md)。用户只要求检测并提示，环境由用户管理；早前安装/Conda 分型要求已被取代。

历史环境要求（已被最新用户决定取代）：[Conda/非 Conda 与双 ISCE 合同](records/2026-09-07-runtime-compatibility-contract.md)。这是兼容要求与缺口核对，不是通用科学安装器已交付。

最新运行修复：[Web 启动环境修复](records/2026-09-07-web-launcher-repair.md)。正式状态改为 `~/.local/state/insar-pilot`；此前 `/tmp` 环境/状态已不存在，不再沿用。

[统一索引](index.md) · [提示词](prompts.md)

更新时间：2026-09-07。最新任务为[工程与 P01 交付](records/2026-09-07-project-p01-release.md)。此处取代旧设计阶段入口；此前记录原样保留在 records/。

## 当前基线

- Web 唯一、Sentinel 优先、单工程 Profile、五页不变。P02—P05 专业内容仍按单页指令开展。
- 启动/刷新进入工程选择，未打开工程仅可检索下载；显式打开 .pilot，新建使用父目录和名称，关闭工程不取消后台任务。
- 新 Web 工程为 data/、processing/<execution_id>/、products/；过程记录在隐藏管理区，旧工程不搬迁。
- P01 保留 ABCD、纯影像地图、EOF/DEM 和三入口获取；目标经预览冻结，项目下载在 data 内发布，Download Only 使用 Library，既有来源可核验后引用。
- 下载任务可发现、暂停/取消/恢复/重试、分页筛选，显示实际保存位置。按尝试保存日志，浏览器事件保留最近 500 条。
- [UI/UX 规范 1.0](../architecture/design-system.md)已经应用于公共外壳、首页、工程入口与 P01；后续页面复用。

## 验证与下一步

本轮最终服务在 8765 运行、无活跃下载/处理/worker，独立测试服务已清理；此为 2026-09-07 瞬时检查。最终检查、平台覆盖、服务状态与清理见[本轮记录](records/2026-09-07-project-p01-release.md)，不可沿用历史任务数。
真实 ASF/CDSE 认证长时吞吐尚未验收；本轮未做 SAR 计算或黄金对照。
后续先读 [P02 卡](pages/p02-data-preparation.md)，按用户指令设计数据准备页面，不自动铺开后续页面。
phase stack 的 D01 合同仍待确定；解缠、广域数值检查、NISAR 新 UI、CUDA 与时序暂缓。
工程搬迁/便携打包、系统文件关联另行处理；单独 .pilot 不包含全部数据。

## 本机环境记录

以下在 2026-09-06 仅核对路径存在，未重新证明所有包/浏览器可运行；临时目录尤其需要任务启动时重查。

| 项目 | 本机位置/事实 |
|---|---|
| WSL 仓库 | `/home/griffin/projects/insar-pilot` |
| Windows 访问 | `\\wsl$\Ubuntu\home\griffin\projects\insar-pilot` |
| Web Python | `/home/griffin/.local/share/insar-pilot/web-venv/bin/python` |
| 原科学/后端测试 Python | `/home/griffin/miniconda3/envs/insar/bin/python` |
| 本机 Web launcher | `/home/griffin/.local/bin/insar-pilot-web` |
| 现有 Linux Node | `/home/griffin/.local/share/insar-pilot/dev-tools/node-v22.14.0-linux-x64/bin/node` |
| Playwright 浏览器缓存 | `/tmp/insar-pilot-playwright` |
| HEAD | `31ccf3afd23c2ea118dfe8bc99c0697bd5f505ec` |
| 工作树 | 有大量原有修改及未跟踪内容，不能 reset/clean；HEAD 不包含全部当前实现 |

开发命令在 WSL 仓库中执行。Windows PowerShell 下使用
`wsl -d Ubuntu --cd /home/griffin/projects/insar-pilot -- <command>`。
Linux 的 rg 在此前环境中不可用，可用 Windows rg 或其他只读搜索方式。

## 工作要求

开始任务先核对服务状态、工作树及选定任务卡。应用状态和科学环境分离；保持用户数据与历史只读。
Python 使用 Web 环境进行新引擎/API 测试；改动代码运行 Ruff/适用类型检查。Web 运行单测、类型构建和定向浏览器检查。
临时路径和旧测试结果仅供定位，不能当作当前环境或任务状态；不输出 token。每项工作新增记录并更新索引。
