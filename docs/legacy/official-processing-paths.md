> LEGACY / HISTORICAL EVIDENCE. Not an active architecture specification.

# 官方处理路径与模块边界

本页是处理层重构的约束文档。目标不是让 Sentinel-1 和 NISAR 共用同一套 SAR
算法，而是让它们共用同一套任务编排、状态、日志、覆盖策略和产品登记机制，同时每个
mission 只保留一条官方数值处理路径。

## 唯一生产路径

| 输入 | 唯一算法入口 | 应用层策略 | 当前接入状态 |
|---|---|---|---|
| Sentinel-1 IW SLC（A/B/C/D） | ISCE2 `stackSentinel.py -W interferogram` | 生成 `run_files/run_*`，按官方顺序逐文件执行 | 已有 legacy 执行，并新增统一单阶段 Task backend |
| NISAR RSLC | ISCE3 `python -m nisar.workflows.insar <runconfig>` | 构造一个官方 runconfig，运行 RIFG/RUNW/GUNW 产品工作流 | CLI/Runner 与统一单产品 Task backend 已接入 |
| ALOS | 无 | 仅检索 | 不进入处理 Registry |

不支持 CEOS/focus、NISAR GSLC，也不建立“自己重写 ISCE 算法”的备用生产路径。可视化是
结果产品上的显式功能，不属于搜索、导入或处理 Task 的自动副作用。

## 模块化边界

```text
LocalSARProduct / ProjectDataCatalog
                 ↓
Compatibility + WorkflowRecipeDescriptor
                 ↓
TaskExecutionApplicationService
  ├─ 参数快照、依赖、覆盖策略、取消、重试、JSONL 日志
  └─ TaskBackend Registry
       ├─ isce2.topsstack → 官方 run_files/run_*
       └─ isce3.nisar_rifg → 官方 nisar.workflows.insar
                 ↓
ResultCatalog
```

“模块化”发生在应用编排层。ESD、geo2rdr、burst resampling、burst IFG、mergeBursts、
dense offsets 和 rubbersheet 等算法阶段仍由 ISCE2/ISCE3 拥有；InSAR-PILOT 不复制这些
实现，也不把它们静态伪装为已经可单独执行的通用 Task。

Sentinel 的官方阶段由 `Isce2TopsStageDiscovery` 从生成后的 `run_files/run_*` 动态投影。
文件名中的数字是执行顺序；每一项依赖前一项。重复序号被视为歧义并拒绝执行。用户仍可选择
一个阶段重跑，但应用不能绕过依赖把另一个自造算法路径插入处理中间。

## ISCE2 TOPS 的 merge 与 product 结论

官方 topsStack `interferogram` 顺序包含两种不同的 merge：

```text
burst coregistration
→ merge reference/coregistered SLC
→ generate burst interferograms
→ merge burst interferograms
→ filter/coherence
→ unwrap
```

因此，“先得到 merged SLC 产品”是官方流程的一部分；但“使用两幅 merged SLC 直接
cross-multiply 生成最终 IFG”不是官方 TOPS 干涉图路径。官方仍逐 burst 生成 IFG，再按
有效区域合并 IFG。

YanAn 真实数据的只读窗口对比显示：`merged reference × conj(merged secondary)` 在多数普通
区域与官方 `fine.int` 相同，但在 burst seam 邻域出现差异，抽样窗口的逐像元完全相同比例为
0.9609375/0.984374，相对 RMSE 约 0.129/0.144，并存在直接算法多出非零像元的窗口。这说明
直接 merged-SLC 成图可作为研究实验，却不能替代官方生产策略。代码中的唯一 Sentinel 策略
因此固定为 `SENTINEL1_TOPS_BURST_IFG_THEN_MERGE`，并且不提供
`MERGE_SLC_THEN_IFG` 生产选项。

应用也不得自动修改 `stackSentinel.py` 生成的 merge 配置。若官方版本在 seam 处出现缺陷，
应保存版本、runconfig、日志和对比证据，作为明确的兼容性修复单独处理，不能静默形成第二条
默认路径。

## 近期完成与剩余工作

本轮已经完成：

- Recipe 增加唯一处理策略和有序依赖校验；同一 mission/product type 不能注册两条 recipe；
- 删除 Sentinel 的静态 `esd/build_interferogram/merge_bursts` 伪 Task；
- 删除 NISAR 的静态 `dense_offsets/rubbersheet` 伪 Task；
- Sentinel 官方 run file 的动态阶段发现、数字排序、歧义拒绝和依赖投影；
- `Isce2TopsStackTaskBackend` 单阶段执行、并行批次、子命令失败传播、取消与结构化日志；
- `NisarIsce3TaskBackend` 从已审计 runconfig 恢复官方产品计划并复用现有 Runner；
- 默认 Task Backend Registry 只登记 ISCE2 TOPS 与 ISCE3 NISAR 两个 canonical adapter；
- 移除运行前自动改写 ISCE2 merge config 的非官方行为。

下一步按以下顺序继续：

1. 将旧 `RunController` 的状态持久化迁到统一 `TaskExecutionApplicationService`，保留薄 UI adapter；
2. 统一把 ISCE2 merged SLC/IFG/COH/UNW 和 ISCE3 RIFG/RUNW/GUNW 登记进 ResultCatalog；
3. 修复 COP30 EGM2008 到 WGS84 高程转换的环境探测和失败传播，再进行完整真实数据回归；
4. 后端合同稳定后再接本地 API/Web Workbench，不在此阶段重写 GUI。
