# 工作交接索引

更新：2026-09-07。最新维护任务：[1.5.0 文档、清理与发行](records/2026-09-07-v1.5.0-release.md)。
本目录记录执行事实，产品目标只由当前架构定义。

## 阅读顺序

1. 根 AGENTS、[架构](../architecture/overview.md)、[五页划分](../architecture/sentinel-workbench.md)。
2. [当前交接](current.md)、[实施状态](../architecture/migration.md)。
3. 任务卡及最新记录，然后重查工作树与实时服务状态。

| 任务 | 当前阶段 | 下一步 |
| --- | --- | --- |
| [公共外壳](pages/shell-project-entry.md) | 已实现；本轮 Web 发行清理 | 保持入口、单窗口与后台生命周期合同 |
| [P01 检索与下载](pages/p01-search-download.md) | 已实现并定向测试 | 真实账号长时下载独立验收 |
| [P02 数据与准备](pages/p02-data-preparation.md) | 待详细设计 | 按下一条用户指令设计 |
| [P03 参数与生成](pages/p03-parameters-generation.md) | 待详细设计 | 先确定依赖的产品合同 |
| [P04 运行](pages/p04-run-monitor.md) | 待详细设计 | 沿用 Run/Job 隔离与官方阶段 |
| [P05 成果与 QC](pages/p05-products-qc.md) | 待详细设计 | 围绕已确认 stack 产品组织 |

## 未决与暂缓

D01：phase stack 是配准复数 SLC、缠绕干涉相位或二者，looks/滤波/参考约定仍未确认。影响 P03—P05 和 P02 产品特有约束，不阻挡通用输入准备。
D02：P02—P05 的布局、字段与 API 待逐页设计；五页职责不重开。
NISAR 新 UI/Range 准备、解缠、广域相位/GUNW、CUDA 与时序暂缓。Qt 清理已纳入本轮独立维护任务。

## 证据与接续

- [工程与 P01 实施](records/2026-09-07-project-p01-release.md)
- [环境只检测与提示](records/2026-09-07-runtime-status-ui.md)
- [单窗口与自动接续](records/2026-09-07-single-window.md)
- [本轮清理与发行](records/2026-09-07-v1.5.0-release.md)
- [任务提示词](prompts.md) · [记录模板](template.md)

每项任务新增记录，更新卡、index、current、migration；旧 records 保持不变，不累计历史测试数为本轮结果。
之前累加的索引全文保存在 `archive/guidance/2026-09-07-before-v1.5.0/`。
