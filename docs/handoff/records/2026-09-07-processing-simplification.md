# 公共外壳｜processing 分区简化
日期：2026-09-07。
本次用户指令与范围：合并 processing 类型，过程文档保存但不明显展示，后续按需调用。
阶段：设计修订。
页面任务卡：[公共入口](../pages/shell-project-entry.md)。
上一份：[工程规划](2026-09-07-project-lifecycle-design.md)，原样保留。

## 接受的决定与仍未知的事项
- 用户已明确减少分区、保留过程证据、按需展示。
- 本轮具体落点为 processing/<execution_id> 与 .insar_pilot/records；详细日志展示入口后续设计。
- 启动先选工程、无工程仅 P01、数据归属和旧工程兼容方案保持。

## 实际完成
- 更新[统一方案](../../architecture/project-lifecycle-layout.md)，删除四类可见分区，保留每次执行隔离。
- 准备成果复用仍须发布/登记；官方 run_files/原生日志保持官方布局，冻结记录归档到隐藏管理区。
- 默认只展示步骤、状态和成果；日志/快照不独立成栏目，按 ID 分页只读调用；失败摘要不隐藏。
- 同步 storage、GUI、migration、index、current、公共任务卡。
- 7 份修改前指导与 SHA-256 清单保存到 archive/guidance/2026-09-07-before-processing-simplification/。
- 没有产品代码/API 改动或实际目录迁移；没有修改用户数据、科学参数或历史记录。

## 验证与证据
- 本轮为文档任务；不运行软件、浏览器或科学计算测试。
- MkDocs strict 构建通过；82 个相对链接与 7 份归档 SHA-256 检查通过。

## 服务与任务
- 未启动或停止服务、worker、下载，没有自管测试进程。
- 本轮结束实时核对：RUNNING，0 下载任务、0 处理任务、0 worker；用户服务保持原状。

## 下一步
- 从本记录与当前方案接续；先实施启动/工程状态，之后实施简化后的布局。
- 不实现已被替换的四类 processing 分区；不把隐藏记录当成可删除缓存。
- index、current、任务卡、migration 已更新；其他页职责保持。
