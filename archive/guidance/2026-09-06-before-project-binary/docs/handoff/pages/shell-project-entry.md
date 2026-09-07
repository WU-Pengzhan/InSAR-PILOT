# 公共外壳｜工程文件入口
状态：2026-09-06 第一轮实现与定向检查完成；不等于 P02 页面已设计。
[交接索引](../index.md) · [当前合同](../../architecture/project-file-entry.md) · [最新实施记录](../records/2026-09-06-project-file-implementation.md)。
已实现：命名 .pilot 新建、文件选择打开、识别、最近工程、legacy 导入；保留已有 project.pilot 和目录 API 兼容。
入口：infrastructure/project_file.py、engine_store.py、application_state.py；web/api.py；frontend/src/ProjectEntry.vue、FilePicker.vue。
验证：75 项 Python、15 项前端单元测试、Ruff/Mypy、类型/构建及三浏览器定向检查，详见记录，不合并不同轮次为全量结果。
下一步：用户使用本轮入口；搬迁/备份/系统关联另行指令，不自动进入 P02 全页。
旧设计记录：[设计提案](../records/2026-09-06-project-file-design.md)。
