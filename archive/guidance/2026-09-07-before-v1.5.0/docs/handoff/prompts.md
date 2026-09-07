# 每页任务提示词

[交接索引](index.md) · [已确认页面划分](../architecture/sentinel-workbench.md)

以下五段是**设计阶段提示词**，可分别发到同一任务或新的仓库任务。
它们指向持久化交接索引，不依赖旧聊天内容。先从 P01 开始；每次只选择一页。
详细布局设计完成后，可使用本文末尾的实现/继续模板。
五页职责已确认，设计任务不重新要求确认页面数量；D01 科学产品选择仍单独处理。

## P01｜检索与下载

```text
请开始 InSAR-PILOT P01「检索与下载」的设计任务。
先读取根 AGENTS.md、docs/handoff/index.md、docs/handoff/current.md，
再读取 docs/handoff/pages/p01-search-download.md 的最新交接及其链接记录，
并按 docs/architecture/sentinel-workbench.md 已确认的五页边界开展工作。

本次只设计 P01，重点是AOI、日期、Sentinel ABCD 与任务专属筛选、纯影像地图、场景选择、下载清单及控制。
先核对实际代码和已有功能，明确复用内容、缺口、页面布局、关键操作、
空/加载/失败状态、输入输出、必要 API 合同和验收方案。
第一个开展的页面。phase stack 类型未确认不阻挡本页设计。
暂不修改产品代码或实施其他页面，不启动真实下载或重型科学计算；
如有影响科学语义的未决项，集中提出并继续不受其影响的设计。

交付可审阅的本页设计文档，保存到 docs/handoff/records/，
更新本页任务卡“最新交接”、docs/handoff/index.md、current.md 和必要的 migration 状态，
最后给出设计、未决项及交接记录链接，完成后停在本页。
```

## P02｜数据与准备

```text
请开始 InSAR-PILOT P02「数据与准备」的设计任务。
先读取根 AGENTS.md、docs/handoff/index.md、docs/handoff/current.md，
再读取 docs/handoff/pages/p02-data-preparation.md 的最新交接及其链接记录，
并按 docs/architecture/sentinel-workbench.md 已确认的五页边界开展工作。

本次只设计 P02，重点是SLC/SAFE、Library/本地目录、参考影像、EOF、DEM、AOI/IW/burst、兼容性与准备状态。
先核对实际代码和已有功能，明确复用内容、缺口、页面布局、关键操作、
空/加载/失败状态、输入输出、必要 API 合同和验收方案。
先读取 P01 最新交接；独立本地导入仍需可用。phase stack 未确认不阻挡通用输入管理，但相关产品特有约束不可猜测。
暂不修改产品代码或实施其他页面，不启动真实下载或重型科学计算；
如有影响科学语义的未决项，集中提出并继续不受其影响的设计。

交付可审阅的本页设计文档，保存到 docs/handoff/records/，
更新本页任务卡“最新交接”、docs/handoff/index.md、current.md 和必要的 migration 状态，
最后给出设计、未决项及交接记录链接，完成后停在本页。
```

## P03｜参数与生成

```text
请开始 InSAR-PILOT P03「参数与生成」的设计任务。
先读取根 AGENTS.md、docs/handoff/index.md、docs/handoff/current.md，
再读取 docs/handoff/pages/p03-parameters-generation.md 的最新交接及其链接记录，
并按 docs/architecture/sentinel-workbench.md 已确认的五页边界开展工作。

本次只设计 P03，重点是专业参数表单、参数解释、目标产品、RuntimeProfile、preflight、Generate 和官方 run-file 预览。
先核对实际代码和已有功能，明确复用内容、缺口、页面布局、关键操作、
空/加载/失败状态、输入输出、必要 API 合同和验收方案。
先读取 P02 交接。最终产品终点与依赖它的 Generate 合同需要 phase stack 决定；若仍未知，先做不依赖该决定的表单/合同审计，并集中询问这一个科学选择。
暂不修改产品代码或实施其他页面，不启动真实下载或重型科学计算；
如有影响科学语义的未决项，集中提出并继续不受其影响的设计。

交付可审阅的本页设计文档，保存到 docs/handoff/records/，
更新本页任务卡“最新交接”、docs/handoff/index.md、current.md 和必要的 migration 状态，
最后给出设计、未决项及交接记录链接，完成后停在本页。
```

## P04｜运行

```text
请开始 InSAR-PILOT P04「运行」的设计任务。
先读取根 AGENTS.md、docs/handoff/index.md、docs/handoff/current.md，
再读取 docs/handoff/pages/p04-run-monitor.md 的最新交接及其链接记录，
并按 docs/architecture/sentinel-workbench.md 已确认的五页边界开展工作。

本次只设计 P04，重点是官方阶段、子命令批次、Run/Job、逐步基础检查、日志、取消与重跑。
先核对实际代码和已有功能，明确复用内容、缺口、页面布局、关键操作、
空/加载/失败状态、输入输出、必要 API 合同和验收方案。
先读取 P03 交接。可用合成命令/fixture 验证调度与界面；真实阶段范围必须消费已确认计划，不能自行扩展到解缠。
暂不修改产品代码或实施其他页面，不启动真实下载或重型科学计算；
如有影响科学语义的未决项，集中提出并继续不受其影响的设计。

交付可审阅的本页设计文档，保存到 docs/handoff/records/，
更新本页任务卡“最新交接”、docs/handoff/index.md、current.md 和必要的 migration 状态，
最后给出设计、未决项及交接记录链接，完成后停在本页。
```

## P05｜成果与 QC

```text
请开始 InSAR-PILOT P05「成果与 QC」的设计任务。
先读取根 AGENTS.md、docs/handoff/index.md、docs/handoff/current.md，
再读取 docs/handoff/pages/p05-products-qc.md 的最新交接及其链接记录，
并按 docs/architecture/sentinel-workbench.md 已确认的五页边界开展工作。

本次只设计 P05，重点是phase stack 场景/配对、影像显示、metadata/lineage、基础有效性与按需局部 QC。
先核对实际代码和已有功能，明确复用内容、缺口、页面布局、关键操作、
空/加载/失败状态、输入输出、必要 API 合同和验收方案。
先读取 P04 交接。通用只读成果列表可先设计；具体 stack 完整性与显示语义取决于产品合同，不能用当前文件名猜测。
暂不修改产品代码或实施其他页面，不启动真实下载或重型科学计算；
如有影响科学语义的未决项，集中提出并继续不受其影响的设计。

交付可审阅的本页设计文档，保存到 docs/handoff/records/，
更新本页任务卡“最新交接”、docs/handoff/index.md、current.md 和必要的 migration 状态，
最后给出设计、未决项及交接记录链接，完成后停在本页。
```

## 设计认可后：实现本页

把 P0N 替换为 P01—P05 中的一页。若用户反馈包含具体调整，直接附在提示词后。

```text
我认可 P0N 最新交接中链接的页面设计，请现在实现本页。
先读取根 AGENTS.md、docs/handoff/index.md、current.md 和该页任务卡，
核对最新设计、我的补充意见及实际代码。只完成该页及其必需的共享后端改动。
先落实领域/API 合同，再完成 GUI、异常状态及与相邻页面的交付；
按改动运行后端测试、Python 静态检查、前端类型/构建与针对性浏览器验收。
不要重复确认已同意的设计，也不要扩展到下一页、Qt、NISAR 或暂缓的科学评价。
未明确的 phase stack 产品选择不能自行决定；继续不依赖它的工作。
不要为 GUI 验证自动启动真实下载或重型科学处理；使用独立 fixture/临时目录，
真实操作范围如在我本次指令中另有说明则按该范围执行。
保留既有工作与运行历史，完成后新增交接记录并更新任务卡、索引、current 和 migration。
报告实际实现、测试、剩余问题、测试服务清理结果及交接链接，完成后停在本页。
```

## 中途换任务：继续未完成工作

```text
请继续 InSAR-PILOT P0N，沿用我已授权的范围，不从头重新设计。
从 AGENTS.md 和 docs/handoff/index.md 进入，读取 current.md、
本页任务卡最新交接及最近记录，先核对工作树、未完成事项和必要的实时任务状态。
不要把旧记录中的运行状态或测试结果当作当前事实，不要重复已完成工作。
完成剩余授权内容与必要验证；新增交接记录并更新所有索引和状态，停在本页。
```

## 只检查：本页验收

```text
请验收 InSAR-PILOT P0N。读取 AGENTS.md、交接索引、本页最新设计和实现记录，
按照本页验收条件检查实际行为、相关测试及跨页合同。
本次只检查和记录问题，不扩展功能或启动真实重型计算。
明确通过、失败、未测项；新增验收交接记录并更新页面/总索引和 migration。
```
