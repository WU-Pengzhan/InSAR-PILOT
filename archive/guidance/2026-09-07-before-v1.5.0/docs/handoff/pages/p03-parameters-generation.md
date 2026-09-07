# P03｜参数与生成

[交接索引](../index.md) · [任务提示词](../prompts.md) · [已确认页面划分](../../architecture/sentinel-workbench.md)

更新时间：2026-09-06。状态：**待设计**。职责边界已确认，详细布局和 API 方案尚未完成本轮逐页设计。
当前预览版已有可复用功能，不代表本页从零开始，也不代表已经按新方案验收。

## 目标与依赖

本页聚焦：专业参数表单、参数解释、目标产品、RuntimeProfile、preflight、Generate 和官方 run-file 预览。

先读取 P02 交接。最终产品终点与依赖它的 Generate 合同需要 phase stack 决定；若仍未知，先做不依赖该决定的表单/合同审计，并集中询问这一个科学选择。

## 输入与输出

输入：P02 已接受修订及输入角色、用户确认的 phase stack 产品合同、官方 generator/adapter 能力。

输出：解析默认值后的科学参数、RuntimeProfile、官方配置/命令与脚本摘要、冻结输入和修订的计划 ID、范围、新目录与已知资源估计。生成不启动科学执行。

## 本页范围

- 使用“参数设置 / 生成预览”两个子视图，不新增第六主页面。
- 参数有单位、默认值、适用条件和解释；高级 JSON 作为检查入口，不强迫基本操作依靠 JSON。
- 审计现有 stack generator 与官方选项，只展示实际支持的科学方案。
- 让用户核对 Generate、计划预览、提交三者的作用；计划提交可从本页进入 P04 观察。

排除范围：不暗定 SLC/干涉相位终点、looks、滤波或参考约定；不修解缠、不自写数值算法、不伪造官方 run files。

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

- 实际生成命令、顺序和有效参数来自官方能力；预览与提交引用同一冻结计划。
- 缺输入/不支持参数可解释；工程变更后旧计划提交返回冲突。
- 资源未知则显示未知；Generate 不自动开始全流程处理。
- 必需上游扩展和新工作目录可见；生成验证使用独立临时目录。

## 已核对的代码入口

以下是 2026-09-06 存在的起点，不是限制可修改文件的白名单；修改共享层需说明本页必要性。

- `frontend/src/App.vue`
- `src/insar_pilot/web/api.py`
- `src/insar_pilot/application/engine_processing.py`
- `src/insar_pilot/infrastructure/engine_store.py`
- `src/insar_pilot/services/stack_generator.py`
- `src/insar_pilot/backends/isce2/topsstack.py`
- `src/insar_pilot/domain/engine.py`

## 已有相关测试入口

按实际改动选择，不把文件存在当成测试已通过。缺失的本页专属浏览器用例按需补充。

- `tests/test_stack_generator.py`
- `tests/test_engine_api.py`
- `tests/test_engine_store.py`
- `tests/test_isce2_topsstack_task_backend.py`
- `tests/test_official_processing_paths.py`

## 最新交接

- 当前阶段：待设计；本轮仅建立任务卡。
- 已完成：页面职责确认，输入输出/排除范围/代码与测试入口整理。
- 未完成：详细设计、产品改动、按新设计验收。
- 已知决策/依赖：见上方“目标与依赖”，以及索引中的 D01。
- 验证：本任务卡代码与测试路径检查；未运行本页软件或科学测试。
- 正在运行的服务/下载/worker：本轮未探测，不能继承旧任务状态。
- 下一个动作：收到本页设计提示词后完成上述“设计任务交付”。
- 详细记录：尚无本页设计/实现记录；今后写入 `docs/handoff/records/` 并把链接加入本节及索引。
