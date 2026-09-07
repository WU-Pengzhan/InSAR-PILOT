# P01｜检索与下载

[交接索引](../index.md) · [任务提示词](../prompts.md) · [已确认页面划分](../../architecture/sentinel-workbench.md)

更新时间：2026-09-06。状态：**待验收**。
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

## 最新交接

- 2026-09-06 外壳与 P01 布局反馈已实现；固定五页、工程栏调宽/横滚、环境折叠、底图状态恢复及工程加载不抢导航。见[最新修复记录](../records/2026-09-06-p01-shell-layout.md)。
- 最终定向外壳浏览器验证 8 项 Linux + 4 项 Windows Edge、前端单测 15 项、类型/构建通过。以下保留上一阶段获取能力与验收边界。

- 已实现：ABCD 筛选、AOI、纯影像地图与重试、独立选择篮、统一三入口预览、可选 EOF/整景 DEM、下载历史/控制/补充获取。
- 后端入口：application/acquisition.py、acquisition_aoi.py、acquisition_dem.py、engine_download.py；download/integrity.py、orbit_service.py、cop30_service.py。
- 界面入口新增：AcquisitionDialog.vue、acquisition.ts；共享组件完成必要注册与禁用状态支持。
- 新 API：acquisition-preview、acquisition-commit、resolve-selection、download-network；旧下载/选择 API 保持兼容。
- 定向测试：Python 102、前端单测 13、Linux 浏览器 14、Windows Edge 7；真实公共 C/D EOF 与 ISCE2 解析已核对。
- 验证边界：真实 ASF 整景账号/长时续传/满带宽、多千景压力及原生 125%/150% 缩放未验证；不宣称 A01—A24 全部验收。
- P02 合同：资产保存 product_key、role、plan/attempt、校验依据及 DEM 覆盖/原高程参考；轨道 sidecar 与 partial 隔离，避免 ISCE2 glob 误选。
- 下一步：使用 P01 新版进行整景验收；按新用户指令决定何时进入 P02。D01 不在本轮决定。
- 详细记录：[实现与测试](../records/2026-09-06-p01-implementation.md)；上轮[设计补充](../records/2026-09-06-p01-dem-network-design.md)保留。
