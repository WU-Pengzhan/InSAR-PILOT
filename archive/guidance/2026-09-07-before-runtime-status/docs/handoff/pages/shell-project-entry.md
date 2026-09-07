# 公共外壳｜工程文件入口
状态：2026-09-07 工程生命周期、简化目录与公共视觉已实现并定向验证；不等于 P02 页面已设计。
[交接索引](../index.md) · [当前合同](../../architecture/project-file-entry.md) · [最新实施记录](../records/2026-09-07-web-launcher-repair.md)。
已实现：命名 .pilot 新建、文件选择打开、识别、最近工程、legacy 导入；保留已有 project.pilot 和目录 API 兼容。
入口：infrastructure/project_file.py、engine_store.py、application_state.py；web/api.py；frontend/src/ProjectEntry.vue、FilePicker.vue。
验证：75 项 Python、15 项前端单元测试、Ruff/Mypy、类型/构建及三浏览器定向检查，详见记录，不合并不同轮次为全量结果。
下一步：用户使用本轮入口；搬迁/备份/系统关联另行指令，不自动进入 P02 全页。
旧设计记录：[设计提案](../records/2026-09-06-project-file-design.md)。

2026-09-06 追加二进制封装：新建/保存默认写容器，旧 JSON 打开不改写、下次软件保存转换，旧 GUI 源不变。最新验收结果以封装记录为准，上一轮入口结果不合并计算。

## 最新任务（2026-09-07）：生命周期与目录分区设计

[最新交接](../records/2026-09-07-project-lifecycle-design.md) · [具体方案](../../architecture/project-lifecycle-layout.md)。本轮仅设计，既有 .pilot 入口/二进制实现保留。启动先选工程、NO_PROJECT 仅 P01 为用户明确要求；新 data/processing/products 布局和项目数据归属为具体建议。下一次先实现入口状态与守卫，再单独实施目录/下载目标，不自动迁移旧工程或推进 P02 全页。

最新设计修订：[processing 简化](../records/2026-09-07-processing-simplification.md)。不再实施 preparation/plans/workspaces/runs 四类可见分区；采用 processing/<execution_id> + 隐藏过程记录。产品未改动，先入口再目录的任务顺序保持。

## 当前实现基线（2026-09-07）

[最新交接](../records/2026-09-07-project-p01-release.md)：启动首页、无工程守卫、关闭清理、原子选中/过期响应防护、布局 2/旧布局兼容及视觉已接线。ProjectLayout 为新增路径入口；过程记录默认隐藏。旧方案不再是待实施状态，搬迁/便携备份仍独立。

## 启动环境修复
[最新记录](../records/2026-09-07-web-launcher-repair.md)：持久 Web Python 和用户级 launcher 已修复，默认应用状态退出 /tmp；工程/P01 功能合同保持。

## 双 ISCE 安装兼容要求
[最新合同核对](../records/2026-09-07-runtime-compatibility-contract.md)：区分 Web 启动和科学可用性，非 Conda 执行与统一安装门禁仍待实现，详见当前 runtime-support 规范。
