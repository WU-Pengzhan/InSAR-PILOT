# P01｜检索与下载

[交接索引](../index.md) · [任务提示词](../prompts.md) · [已确认页面划分](../../architecture/sentinel-workbench.md)

更新时间：2026-09-06。状态：**设计待评审**。[详细设计](../../architecture/p01-search-download.md)已保存，包含布局、交互、接口缺口及验收矩阵；最新增加[可选 EOF/整景 DEM 与网络评估](../../architecture/p01-ancillary-downloads.md)，前版方向已获认可，补充方案待评审。本轮未修改产品代码。
当前预览版已有可复用功能，不代表本页从零开始，也不代表已经按新方案验收。

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

- 当前阶段：设计待评审；前版方向获认可，新增 EOF/DEM 及网络补充已保存，未实现产品。
- 用户要求：三入口统一勾选 EOF/DEM；DEM 包住所选完整 SLC 幅宽、多 frame 联合范围并留安全余量。
- 建议初值：EOF 默认开、DEM 默认关；COP30、整景联合 + 20 km；网络有限并发。20 km/默认勾选/并发参数为本次建议，非已验证科学保证。
- 已完成：静态审计、2 项本地行为探针、24 MiB 公开 DEM Range 测试及设计补充；新增 A17—A24 验收要求。
- 必修缺口：S1D EOF 被识别成 S1A；非空坏 SLC 可被 skipped；旧 DEM 只围绕选中 burst 扩展；Web DEM 未接线。
- 未完成：上述缺口修复、Web EOF/DEM 选项、DEM 新规划、ASF 真实下载/长时测速和产品验收。
- 跨页：P02 新增 DEM 源/范围/余量/版本/原高程参考与覆盖报告；高程转换和处理适用性仍归 P02。
- 验证与瞬时服务状态：见最新记录；未启动用户任务或修改代理，未访问科学输入。
- 下一动作：按主设计和补充稿先补 EOF 正确匹配、文件校验、选择/获取/DEM 合同，再实现界面与统一调度；仅推进 P01。
- 详细记录：[EOF/DEM 与网络评估](../records/2026-09-06-p01-dem-network-design.md)。
- 前记录：[P01 初版设计](../records/2026-09-06-p01-search-download-design.md)，保留不改写。
