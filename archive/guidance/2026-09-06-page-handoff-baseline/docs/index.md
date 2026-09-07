# InSAR-PILOT Web 工作台

当前方向：**Web 唯一产品端，先 Sentinel-1，后 NISAR；按页面逐步设计与实施。**

- [当前范围与架构](architecture/overview.md)
- [实施进度与暂缓事项](architecture/migration.md)
- [Sentinel 五页面讨论提案](architecture/sentinel-workbench.md)
- [当前资产与指导清理](architecture/current-state.md)
- [Web 使用与退出](user-guide.md)

近期目标是取得 phase stack，具体科学产品待确认。解缠和大范围相位检查暂缓；
基础文件、输入兼容性、执行状态和成果结构检查保留。

已有检索下载、工程、文件选择、任务控制、基础成果/QC 与退出功能。
当前仍是预览版，页面提案不等于全部实现。PySide6/Qt 界面停止开发，
旧安装、教程、CLI 和桌面说明保留作历史参考；当前入口使用 `insar-pilot-web`。
安装包依赖与旧默认入口的技术清理另行安排。
