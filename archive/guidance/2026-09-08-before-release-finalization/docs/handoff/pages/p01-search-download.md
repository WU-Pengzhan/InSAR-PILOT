# P01｜检索与下载

[交接索引](../index.md) · [任务提示词](../prompts.md) · [已确认页面划分](../../architecture/sentinel-workbench.md)

更新时间：2026-09-07。状态：**已实现并定向测试，真实长时下载待验收**。
用户已授权完整实现本页；本轮交付与实际验证见[实现记录](../records/2026-09-06-p01-implementation.md)。
[主设计](../../architecture/p01-search-download.md)与[EOF/整景 DEM 方案](../../architecture/p01-ancillary-downloads.md)同步实现决策。

## 目标与依赖

本页聚焦：AOI、日期、Sentinel ABCD 与任务专属筛选、纯影像地图、场景选择、下载清单及控制，并包含可选 EOF 与覆盖完整 SLC 的 DEM 获取。

第一个开展的页面。phase stack 类型未确认不阻挡本页设计。

## 输入与输出

输入：全局/工程入口、AOI、时间范围、平台/轨道/模式/极化筛选、当前工程 Profile 和可用下载环境。

输出：精确场景身份与选择、获取计划、下载尝试/文件状态、可用 Library 引用；交给 P02 的是有来源和状态的数据，不是含糊的目录字符串。

## 本页范围

- 保留 Leaflet 纯影像底图和必要署名；设计筛选、地图、结果、选中清单与下载任务的布局。
- 覆盖从选择创建工程、添加兼容工程、仅下载三种入口；Sentinel ABCD 可多选，空选明确处理。
- 清晰展示完整 SLC 与可选 EOF/DEM、整景联合范围/余量、路径、准备/传输/拼接状态、已知进度和暂停/继续/取消/重试。
- 保留既有 NISAR/All 分组行为，但不开发新的 NISAR 专属体验。

排除范围：不做 P02 的完整本地兼容报告，不改科学参数，不新增 NISAR Range 子集流程，不默认启动用户真实 SAR 下载。

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

- 筛选请求准确、空选与失效选择可解释；过期搜索响应不能覆盖最新选择。
- 相同场景的继续/重试不重复提交，历史尝试/partial 保留；下载入口始终可找到。
- 底图失败时 AOI/结果仍可用；完整 SLC 检索/下载不能标为 burst 子集下载。
- 三种数据入口向 P02 交付相同语义的身份/状态；跨 Profile 绑定被拒绝。

## 已核对的代码入口

以下是 2026-09-06 存在的起点，不是限制可修改文件的白名单；修改共享层需说明本页必要性。

- `frontend/src/DataExplorer.vue`
- `frontend/src/SearchMap.vue`
- `frontend/src/DownloadJobs.vue`
- `frontend/src/App.vue`
- `src/insar_pilot/web/api.py`
- `src/insar_pilot/application/engine_data.py`
- `src/insar_pilot/application/engine_download.py`
- `src/insar_pilot/application/engine_download_control.py`
- `src/insar_pilot/download/download_service.py`

## 已有相关测试入口

按实际改动选择，不把文件存在当成测试已通过。缺失的本页专属浏览器用例按需补充。

- `tests/test_web_explorer.py`
- `tests/test_web_download_controls.py`
- `tests/test_asf_sentinel_adapter.py`
- `frontend/e2e/explorer.spec.ts`
- `frontend/e2e/downloads.spec.ts`

## 当前实施与最新交接

最新维护：[1.5.0 清理与发行](../records/2026-09-07-v1.5.0-release.md)。功能基线：[工程与 P01 交付](../records/2026-09-07-project-p01-release.md)。
已实现 ABCD、AOI、纯影像地图、跨检索选择篮、三入口预览、EOF/整景 DEM、下载控制、来源复用和历史分页。
新增实现入口：application/acquisition.py、acquisition_storage.py、acquisition_dem.py；frontend/src/AcquisitionDialog.vue、acquisition.ts。
项目/Library 目标在预览中冻结，切换工程不重定向。P02 接收有身份、角色、校验/来源与覆盖记录的资产，不把下载完成等同于科学输入就绪。
真实 ASF/CDSE 认证长时吞吐、长时续传与压力验收仍未完成；详见原始实施记录，不将模拟用例替代真实下载。
下一步由用户决定真实获取验收或进入 P02 设计；本次清理不改变 D01 或推进后续页面。
