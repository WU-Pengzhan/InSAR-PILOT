# P02｜数据与准备

[交接索引](../index.md) · [任务提示词](../prompts.md) · [已确认页面划分](../../architecture/sentinel-workbench.md)

更新时间：2026-09-06。状态：**待设计**。职责边界已确认，详细布局和 API 方案尚未完成本轮逐页设计。
当前预览版已有可复用功能，不代表本页从零开始，也不代表已经按新方案验收。

## 目标与依赖

本页聚焦：SLC/SAFE、Library/本地目录、参考影像、EOF、DEM、AOI/IW/burst、兼容性与准备状态。

先读取 P01 最新交接；独立本地导入仍需可用。phase stack 未确认不阻挡通用输入管理，但相关产品特有约束不可猜测。

2026-09-06 新增上游依赖（仅记录合同，不开展 P02 设计）：见 [P01 设计](../../architecture/p01-search-download.md)与[交接记录](../records/2026-09-06-p01-search-download-design.md)。P01 将交付场景复合身份、查询/AOI 来源、获取计划、SLC/EOF 文件角色、Library asset/version 和获取/校验状态。远程选择、partial、待校验与可用资产须分开；P01 查询 AOI 不自动覆盖处理 AOI。P02 继续负责处理 AOI、参考影像、轨道/DEM 和 IW/burst 兼容性；上游新合同尚未实现，现有本地导入入口保留。

最新 P01 补充见[EOF/DEM 与网络评估](../../architecture/p01-ancillary-downloads.md)及[最新记录](../records/2026-09-06-p01-dem-network-design.md)。P01 新增可选整景 DEM 获取，交付源瓦片/版本、整景联合几何、余量、原始高程参考和缺片/nodata 报告。P02 仍负责高程基准转换证据、处理格式、覆盖检查与就绪判定；COP30 GeoTIFF 已下载不等于可直接用于 ISCE。本页仍未开展详细设计。

## 输入与输出

输入：P01 获取结果或已有本地/Library 数据，工程配置修订、AOI 和运行环境可用性。

输出：版本化 processing Dataset、参考/secondary 角色、EOF/DEM 引用、兼容性原因与准备状态。参考影像、DEM 和 AOI 只保留一份工程权威设置，供 P03 冻结。

## 本页范围

- 提供下载所得与已有本地数据入口，复用服务端文件选择器。
- 识别产品身份和输入角色，显示缺失、重复、不可读、变更和不兼容原因。
- 组织参考影像、时间/轨道、AOI/IW/burst 共同覆盖及 DEM/EOF 状态。
- 审计已有轨道/DEM 准备能力，区分已接线、可复用与未实现；重型准备走 Job。

排除范围：不重新设计 P01 检索，不在 P02 提供另一套科学处理参数，不自动改变 DEM 垂直基准或在线下载，不开展 NISAR 准备。

## 设计任务交付

核对真实现状并列出复用/缺口；给出布局、信息层级、关键操作、正常/空/加载/失败状态、
后端/API 合同变化、跨页交付和验收方案。可提供草图或独立原型，不改产品页面实现。
只集中提出影响科学语义或重大交互的未决问题，不重复询问已经接受的五页划分。

## 实现任务交付

收到明确的本页实现指令后，在已认可设计基础上完成必要 backend/API 和 GUI；
覆盖相关错误状态、执行适当测试并记录实际结果。常规实现选择自主处理。
若用户同时要求设计与实现且范围明确，直接完成授权范围，不人为再加批准轮次。
完成本页后停下，不自动启动下一页。

## 本页验收重点

- 首次数据绑定锁定 Profile，混合 mission 不能进入一个 processing Dataset。
- 选择文件夹、返回修改、刷新后状态保持一致；路径可用性不等于内容兼容。
- 缺轨道、缺 DEM、垂直转换不可证实等基础问题不能标为就绪。
- 输入/参考修改形成新修订，后续旧计划过期，历史成果不覆盖。

## 已核对的代码入口

以下是 2026-09-06 存在的起点，不是限制可修改文件的白名单；修改共享层需说明本页必要性。

- `frontend/src/App.vue`
- `frontend/src/FilePicker.vue`
- `frontend/src/FilePathField.vue`
- `src/insar_pilot/web/file_browser.py`
- `src/insar_pilot/application/engine_data.py`
- `src/insar_pilot/infrastructure/engine_store.py`
- `src/insar_pilot/services/product_compatibility.py`
- `src/insar_pilot/services/dem_preparer.py`

## 已有相关测试入口

按实际改动选择，不把文件存在当成测试已通过。缺失的本页专属浏览器用例按需补充。

- `tests/test_web_file_browser.py`
- `tests/test_engine_store.py`
- `tests/test_product_compatibility.py`
- `tests/test_local_import_application.py`
- `frontend/e2e/file-picker.spec.ts`

## 最新交接

- 当前阶段：待设计；初始任务卡保留，2026-09-06 仅补充 P01 上游合同依赖。
- 已完成：页面职责确认，输入输出/排除范围/代码与测试入口整理。
- 未完成：详细设计、产品改动、按新设计验收。
- 已知决策/依赖：见上方“目标与依赖”，以及索引中的 D01。
- 验证：本任务卡代码与测试路径检查；未运行本页软件或科学测试。
- 正在运行的服务/下载/worker：本轮未探测，不能继承旧任务状态。
- 下一个动作：收到本页设计提示词后完成上述“设计任务交付”。
- 详细记录：尚无本页设计/实现记录；今后写入 `docs/handoff/records/` 并把链接加入本节及索引。
