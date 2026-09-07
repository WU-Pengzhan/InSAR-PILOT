# Pipeline、计划与状态

Sentinel 和 NISAR 共享执行基础设施，拥有独立定义。
当前先完善 Sentinel；页面划分见 [已确认页面划分](sentinel-workbench.md)，不是新的科学阶段定义。

## 状态合同

Run：QUEUED → RUNNING → SUCCESS / FAILED / CANCELLED；QUEUED 可直接 CANCELLED。
终态不可改写，重试创建新 Run/Job。

Step 是当前配置视图：NOT_READY、READY、QUEUED、RUNNING、SUCCESS、FAILED、
STALE、SKIPPED、CANCELLED。执行状态与已有 active 成果是否仍可用分别显示。
SKIPPED 只适用于定义中允许的不适用步骤，不能掩盖必需依赖。

Artifact 的完整性、可访问性、当前适用性独立：
UNVERIFIED/VALID/INVALID，AVAILABLE/MISSING，CURRENT/STALE。
旧 Run SUCCESS 不因输入变化而改为 STALE。

## 签名与提交

科学签名包括定义/策略版本、有效科学参数、精确输入版本与指纹、处理器/模板/相关环境。
输入或上游 active 变化沿依赖图传播；布局和配色不触发重算。
QC 策略变化仅重评门禁。昂贵科学检查暂缓时，不默认增加新的阈值或全景计算。

Generate/预览给出计划 ID、修订、输入、执行范围、新目录和已知资源估计。
提交引用该计划；过期计划拒绝提交。执行期间的工程修改不影响冻结计划。
成功结果只有满足当前产品合同、必要门禁且签名匹配，才原子成为 active。

## 隔离与重跑

每个 Execution 使用独占新工作空间；官方 TOPS 序列可在内部共享工作目录。
每个已发布步骤成果和 sidecar 闭包必须冻结；后续步骤仅修改工作副本。
使用 copy/reflink，不用 hard link 隔离历史。

未经读写审计的中间检查点不用于跳过上游。计划显式说明扩大后的重算范围。
NISAR 后续仍按官方 workflow 整体重跑，不把内部进度阶段当恢复入口。

## 当前范围改变的含义

近期目标到约定的 phase stack，解缠与深度相位数值评价暂缓。
实际终点由产品合同和官方生成计划共同决定；不能仅把已有失败阶段隐藏就宣称完整成功。
本次指导更新没有修改默认处理参数、stage 列表或后端执行范围。
