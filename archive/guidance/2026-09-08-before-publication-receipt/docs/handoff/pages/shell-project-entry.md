# 公共外壳｜工程与应用入口

更新：2026-09-07。已实现工程生命周期与单窗口，最新维护为 [1.5.0 清理发行](../records/2026-09-08-v1.5.0-finalization.md)。

## 当前能力

命名 .pilot 新建、打开、最近工程、旧格式导入与二进制封装；启动工程选择，未打开只可检索下载。新布局 data/processing/products，旧布局兼容。关闭工程不取消后台。
任意浏览器直连，一个窗口占用，其余自动等待。运行环境只检测组件与原因，不安装环境。
1.5.0 默认命令转 Web，移除 Qt 专属界面/启动/依赖，保留旧工程服务。

## 合同与实现入口

[工程文件](../../architecture/project-file-entry.md) · [布局](../../architecture/project-lifecycle-layout.md) · [运行环境](../../architecture/runtime-support.md) · [Run/Job](../../architecture/run-job-model.md)

infrastructure/project_file.py、project_layout.py、project_codec.py、engine_store.py；web/launch.py、api.py、window_lease.py；frontend/src/ProjectEntry.vue、SingleWindow.vue。

## 验证与下一步

当前证据：[本轮清理](../records/2026-09-08-v1.5.0-finalization.md)。功能原始记录：[工程/P01](../records/2026-09-07-project-p01-release.md)、[单窗口](../records/2026-09-07-single-window.md)。不合并不同轮次为全量结果。
搬迁、便携备份与系统关联仍为独立工作，不自动进入 P02。
