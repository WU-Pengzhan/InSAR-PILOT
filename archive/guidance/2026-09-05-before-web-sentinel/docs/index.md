# InSAR-PILOT

<p align="center">
  <img src="assets/branding/logo.png" width="560" alt="InSAR-PILOT logo">
</p>

**InSAR-PILOT** 是 **InSAR Processing Interface and Lightweight Orchestration Toolkit** 的缩写，即“面向 InSAR 处理的轻量级图形界面与流程编排工具”。它是一个开源、窗口化的 SAR/InSAR 处理工作台，用**项目文件夹**组织数据下载、轨道/DEM 准备、参数配置、流程执行与 quicklook 预览。

当前版本聚焦 Sentinel-1 与 [ISCE2](https://github.com/isce-framework/isce2) TOPS stack 工作流。InSAR-PILOT **不重新实现** SAR 处理算法——真正的数值计算发生在 ISCE2 二进制程序中，本工具负责构造正确的命令、管理输入与状态、监控执行。

![Start page](assets/screenshots/start-page.png)

## 快速导航

- [安装](installation.md) — conda 环境 + pip 安装，WSL2/Ubuntu 说明
- [快速开始](quickstart.md) — GUI 上手最短路径
- [端到端教程](tutorial.md) — 从建项目到出结果的完整走查（GUI 与 CLI 两条路径）
- [命令行 CLI](cli.md) — 无界面服务器上的 `insar-pilot-cli`
- [完整手册](user-guide.md) — 各页面逐一说明
- [架构说明](architecture.md) — 面向贡献者的分层与约定
- [故障排查](troubleshooting.md) — Qt/地图/DEM/run_files 常见问题
- [English documentation](en/index.md)

## 核心功能

- **项目制工作区**：每个项目保存下载数据、处理工作目录、日志、quicklook 和 `project.pilot`。
- **Data Acquisition**：Earthdata 账户检查、ASF Sentinel-1 SLC 查询、场景选择、SLC/EOF 下载、地图与场景表查看。
- **Processing Setup**：数据源、EOF、DEM、AOI/BBox、IW、参考影像、处理参数、preflight 和命令预览集中配置。
- **Run Executor**：发现并执行 `run_files/run_*`，支持 next/selected/remaining 执行，显示 step/subcommand 状态、日志与 exit code。
- **Results Quicklook**：扫描输出结果，预览或导出 SLC、干涉图和 overlay quicklook。
- **无界面 CLI**：`insar-pilot-cli` 复用与 GUI 相同的服务层，`project.pilot` 与 `logs/` 可在两个前端间互换。

## 许可证

本项目使用 [Apache-2.0](https://github.com/WU-Pengzhan/InSAR-PILOT/blob/main/LICENSE) 许可证。InSAR-PILOT 不是 ISCE2 官方项目，不修改 ISCE2 算法，尊重并依赖 ISCE2 的开源工作。
