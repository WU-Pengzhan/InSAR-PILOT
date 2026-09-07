# 当前方向：Web 工作台，Sentinel-1 优先

状态：2026-09-05 产品方向生效，2026-09-06 五页划分获用户同意。此前“同时完善两条 Pipeline、通过解缠/GUNW 对照后才能聚焦 Web”的推进要求已被替代。本文定义当前范围；[实施状态](migration.md)记录完成情况。

## 已确定的产品决策

- Web 是唯一继续开发的产品端，停止 PySide6/Qt 桌面界面开发。旧代码保留为可复用资产和迁移材料，不再要求两端功能同步。
- 本机单用户，Ubuntu 或 WSL2 Ubuntu；浏览器通过 loopback 连接。应用环境与科学处理环境分离。
- 先做好 Sentinel-1 / ISCE2 TOPS 的完整用户体验，再推进 NISAR / ISCE3。现有 NISAR 与 openSEPPO 能力保留。
- 一个工程固定一个传感器/mission Profile；Sentinel 和 NISAR 可以拥有不同的处理页面、参数与科学步骤。
- 近期成果目标是 phase stack。具体是配准后的复数 SLC stack、按影像对组织的缠绕干涉相位 stack，还是二者都要，待用户确认；不能据此自行选择多视或滤波参数。
- 解缠排障、大范围相位数值对照、完整 GUNW 对照、CUDA 与时序后处理暂缓，不作为当前页面开发门槛。
- 基础输入兼容性、文件可读性、形状/资产闭包、真实退出状态仍需检查。暂缓科学评价不等于把缺失数据或失败执行标为成功。
- 五页分工已确认；按单页指令完成设计、必要后端合同、实现和验收，不一次铺开全部功能。每项从交接索引进入并写回交接记录。

## 页面与交接入口

[Sentinel 已确认页面划分](sentinel-workbench.md)包含五个主页面：
检索与下载 → 数据与准备 → 参数与生成 → 运行 → 成果与 QC。

五页职责已确认，详细页面设计和实现逐项开展。Recipe 表达科学方案，页面表达用户任务；二者不强行一一对应。用户可以直接返回任一页，跨页任务由后台持久化。

[工作交接索引](../handoff/index.md)列出 P01—P05 的任务卡、最新交接与下一步；[提示词库](../handoff/prompts.md)提供设计、实现和继续模板。交接文件记录任务事实，不形成第二套架构。

## 技术基础

Vue 3 / TypeScript / Quasar；SAR 检索地图使用 Leaflet，成果空间展示使用 OpenLayers / Proj4js，图表使用 ECharts。后端为 FastAPI REST/WebSocket、Application Services、纯 Python Domain、单机 Job Engine 和 SQLite/文件系统。

统一工程、数据引用、Run/Job、成果、QC 与日志基础设施；不统一两种传感器的科学流程。GUI 不直接运行处理器，官方命令和科学参数语义保持不变。

## 文档职责

| 文档 | 职责 |
|---|---|
| [Current state](current-state.md) | 当前资产、可用程度与本次方向变化 |
| [Migration](migration.md) | 已实现、进行中、待确认和暂缓任务 |
| [Sentinel workbench](sentinel-workbench.md) | 已确认页面职责与未决科学合同 |
| [P01 检索与下载设计](p01-search-download.md) | 本页布局、交互与验收边界；当前实现见交接 |
| [Handoff index](../handoff/index.md) | 单页任务入口、状态、最新交接和提示词 |
| [GUI](gui-architecture.md) | 共享外壳、平台与交互规则 |
| [Sentinel](sentinel1-pipeline.md) / [NISAR](nisar-pipeline.md) | 两种独立科学流程与当前范围 |
| [Domain](domain-model.md) / [Project](project-model.md) | 对象与工程绑定 |
| [Pipeline](pipeline-model.md) / [Run and Job](run-job-model.md) | 执行、状态、计划与重跑 |
| [Artifact](artifact-model.md) / [QC](qc-model.md) | 成果身份、结构检查和分级科学评价 |
| [Data](data-model.md) / [Storage](storage.md) | 获取差异、共享引用和持久化 |

旧指导的原样副本与 SHA-256 清单位于仓库 `archive/guidance/2026-09-05-before-web-sentinel/`。其中的 AGENTS 已改名为归档文件，避免形成嵌套生效指令。日期化复盘是历史快照，不覆盖本文。

当前公共外壳与 P01 视觉采用 [UI/UX 设计规范 1.0](design-system.md)。工程入口/简化目录和数据下载已按[本轮记录](../handoff/records/2026-09-07-project-p01-release.md)完成代码收敛；后续页面沿用规范，科学内容仍逐页开展。

安装和科学环境的跨用户支持以[Runtime 支持合同](runtime-support.md)为准；无需手动 activate 不等于 ISCE2/ISCE3 已就绪。
