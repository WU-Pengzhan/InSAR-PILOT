# 领域模型与页面边界

当前方向见 [overview](overview.md)。共享领域模型服务 Sentinel-first Web，不强制 Sentinel 与 NISAR 使用同一组科学步骤或界面。

| 对象 | 职责 |
|---|---|
| Project / Profile | 工程身份、AOI、配置修订；unassigned / sentinel1_tops / nisar |
| DatasetRevision / Binding | 按 mission 组织的版本化场景集合，以及工程用途引用 |
| Pipeline / StepDefinition | 专业科学流程和稳定步骤定义、输入输出角色、依赖及参数模式 |
| PipelineExecution | 一次冻结的计划、范围和独占工作空间 |
| StepRun | 一次实际步骤执行、输入/参数/环境/命令快照、结果和来源 |
| Job | 排队、进程、取消、心跳和资源；仅下载可无 run_id |
| Artifact / AssetRef | 不可变逻辑成果，以及文件或 HDF5 dataset 等物理引用 |
| QCMetric / QCCheck / QCReport | 事实、解释规则与本次评估；不把未执行检查标 PASS |
| Event / Layer | 有序状态事件与空间成果展示引用 |

关系为 Project → Dataset/Pipeline → Execution → Run → Job；
Run 引用输入/输出 Artifact，QC 引用 Run/Artifact，Layer 引用空间 Artifact。

稳定 ID、带时区 UTC、版本化定义与有限 JSON 值用于可追溯记录。
一次重试不是重写旧 Run；导入数据不虚构创建它的 Run。
同一 HDF5 可支持多个逻辑 Artifact，phase stack 的最终类型仍待确认。

Recipe 是科学策略/计划，不是页面 ID。页面是围绕用户操作对同一模型的不同视图；
页面切换不创建新的科学运行，也不隐式修改已有计划。Domain 不依赖 Qt、FastAPI 或处理器 SDK。
