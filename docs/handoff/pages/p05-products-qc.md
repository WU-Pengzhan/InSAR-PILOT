# P05｜成果与 QC

[交接索引](../index.md) · [任务提示词](../prompts.md) · [已确认页面划分](../../architecture/sentinel-workbench.md)

更新时间：2026-09-06。状态：**待设计**。职责边界已确认，详细布局和 API 方案尚未完成本轮逐页设计。
当前预览版已有可复用功能，不代表本页从零开始，也不代表已经按新方案验收。

## 目标与依赖

本页聚焦：phase stack 场景/配对、影像显示、metadata/lineage、基础有效性与按需局部 QC。

先读取 P04 交接。通用只读成果列表可先设计；具体 stack 完整性与显示语义取决于产品合同，不能用当前文件名猜测。

## 输入与输出

输入：P04 正式登记的 Artifact、资产闭包、Run/QC、配对/场景信息，以及用户确认的产品合同。

输出：可定位的 stack 成员、原始科学资产引用、显示/检查结果及来源；导出 manifest 或其他形式在本页设计中明确，不冒充已经实现。

## 本页范围

- 同页提供“成果 / QC”子视图，与 P04 逐步基础检查引用同一报告。
- 按场景或配对呈现产品类型、日期、looks、网格、来源、active/stale 和完整性。
- 区分复数 SLC、干涉相位和显示派生；图像按窗口/分块/采样读取。
- 有可靠地理定位才放入地图；雷达数组保留影像视图，显式说明缺失元数据。

排除范围：不自动整景相位对照，不恢复解缠/GUNW/CUDA 验收，不新增 SBAS/时序/速度算法，不以 PNG 代替科学 stack。

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

- 逐项展示真实 Artifact；缺成员、missing/invalid/stale 和未知指标可区分。
- window/sample 的位置、nodata、mask、单位与方法可追溯，不伪造 CRS。
- 产品切换/色标/显示不改变科学签名或原文件；原始资产完整可解析。
- 大数据读取有界；界面空/加载/错误/长列表可用，科研未评价不显示 PASS。

## 已核对的代码入口

以下是 2026-09-06 存在的起点，不是限制可修改文件的白名单；修改共享层需说明本页必要性。

- `frontend/src/App.vue`
- `frontend/src/MapWorkspace.vue`
- `frontend/src/ChartWorkspace.vue`
- `src/insar_pilot/web/raster.py`
- `src/insar_pilot/application/engine_qc.py`
- `src/insar_pilot/application/engine_processing.py`
- `src/insar_pilot/infrastructure/asset_closure.py`
- `src/insar_pilot/infrastructure/engine_store.py`

## 已有相关测试入口

按实际改动选择，不把文件存在当成测试已通过。缺失的本页专属浏览器用例按需补充。

- `tests/test_engine_asset_closure.py`
- `tests/test_engine_api.py`
- `tests/test_engine_store.py`
- `tests/test_result_catalog.py`
- `frontend/src/App.test.ts`

## 最新交接

- 当前阶段：待设计；本轮仅建立任务卡。
- 已完成：页面职责确认，输入输出/排除范围/代码与测试入口整理。
- 未完成：详细设计、产品改动、按新设计验收。
- 已知决策/依赖：见上方“目标与依赖”，以及索引中的 D01。
- 验证：本任务卡代码与测试路径检查；未运行本页软件或科学测试。
- 正在运行的服务/下载/worker：本轮未探测，不能继承旧任务状态。
- 下一个动作：收到本页设计提示词后完成上述“设计任务交付”。
- 详细记录：尚无本页设计/实现记录；今后写入 `docs/handoff/records/` 并把链接加入本节及索引。
