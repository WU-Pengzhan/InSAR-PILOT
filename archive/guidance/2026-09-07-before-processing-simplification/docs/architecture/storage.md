# 存储与文档归档

科学存储模型继续使用，不因放弃 Qt 界面而替换 Run/Artifact 历史。

| 位置 | 权威内容 |
|---|---|
| 工程名.pilot（兼容 project.pilot） | 二进制封装的当前工程意图、Profile、数据引用、配置修订 |
| .insar_pilot/state.sqlite | 接受的修订、计划、Run/Job、成果、lineage、QC、active、事件、Layer |
| `runs/<run_id>/` | 冻结快照、官方配置、stdout/stderr/原生日志 |
| `workspaces/<execution_id>/` | 本次执行可变工作文件 |
| `artifacts/<artifact_id>/` | manifest 与不可变资产闭包 |
| cache/ | 可重建的预览、瓦片和统计 |
| 应用库 / Library 库 | 偏好、最近工程、RuntimeProfile、全局下载 / 共享数据身份及位置 |

SQLite 使用外键、WAL、超时、迁移和显式事务；单写者与本地可靠锁。
WSL 工程状态默认放 Linux 文件系统。不要在多库保存两份任务权威状态。

工程修订先写 durable pending，再原子替换文件并提交接受修订/事件；恢复对比摘要后才调度。
成果先暂存、检查闭包、写 manifest、原子发布，再事务登记终态/QC/active/事件。
孤立文件须结合执行证据核对，不能从文件存在推断成功。

凭据不进快照；可变工作与冻结历史用独立 copy/reflink，不用 hard link。
缓存清理不得删除输入、成果或历史日志。日志容量管理应归档/分段并保留引用，不覆盖 Run 证据。

## 指导文件归档

本轮将旧指导和基线按清单复制到
`archive/guidance/2026-09-05-before-web-sentinel/`，保存 SHA-256。
该目录是历史材料，不是有效规范；不在其中保留会自动生效的 AGENTS.md 文件名。
只归档清单中的文件，不宣称已备份全部源代码、环境或科学数据。
仓库外 Skills 和插件不属于项目文档清理范围。

Web 工程文件入口与身份检查见[工程文件合同](project-file-entry.md)。历史和资产目录布局不变，单独复制 .pilot 不构成完整备份。

2026-09-06 .pilot 默认写入带版本与完整性校验的二进制容器，读取兼容旧 JSON；打开不转换，软件下次保存配置时转换。仅工程描述采用封装，SQLite/Run/Artifact 文件格式不变，见[容器合同](project-file-entry.md)。

## 新工程分区设计（2026-09-07）

上表为已实现物理布局；[新方案](project-lifecycle-layout.md)建议新工程采用 data、processing、products，并以独立布局版本兼容旧根目录。目录变更尚未实施；不可覆盖历史或打开时搬迁。
