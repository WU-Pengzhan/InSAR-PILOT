# InSAR-PILOT

<p align="center">
  <img src="docs/assets/branding/logo.png" width="640" alt="InSAR-PILOT logo">
</p>

**InSAR-PILOT** 是 **InSAR Processing Interface and Lightweight Orchestration Toolkit** 的缩写，中文可理解为“面向 InSAR 处理的轻量级图形界面与流程编排工具”。

**副标题：Open Desktop Workbench for Guided SAR/InSAR Processing**

[English](README_EN.md) | [完整中文手册](docs/USER_GUIDE.md) | [故障排查](docs/TROUBLESHOOTING.md)

[![CI](https://github.com/WU-Pengzhan/InSAR-PILOT/actions/workflows/ci.yml/badge.svg)](https://github.com/WU-Pengzhan/InSAR-PILOT/actions/workflows/ci.yml) [![CodeQL](https://github.com/WU-Pengzhan/InSAR-PILOT/actions/workflows/codeql.yml/badge.svg)](https://github.com/WU-Pengzhan/InSAR-PILOT/actions/workflows/codeql.yml) [![License](https://img.shields.io/badge/License-Apache%202.0-blue)](LICENSE) [![Python](https://img.shields.io/badge/Python-3.10%2B-blue)](https://www.python.org) [![ISCE2](https://img.shields.io/badge/Powered%20by-ISCE2-2f6db3)](https://github.com/isce-framework/isce2)

InSAR-PILOT 是一个开源、窗口化的 SAR/InSAR 处理工作台，用项目文件夹组织数据下载、轨道/DEM 准备、参数配置、流程执行和 quicklook 预览。

当前版本聚焦 Sentinel-1 与 [ISCE2](https://github.com/isce-framework/isce2) TOPS stack 工作流，后续计划扩展到更多 SAR 载荷和时序 InSAR 流程。项目主要由 Codex 辅助开发，并经过人工迭代审查。

> 发布说明：v1.0.0 是首个正式发布版。建议先使用小范围样例项目验证运行环境、数据下载和处理结果，再进入正式生产流程。

## 界面预览

![Start page](docs/assets/screenshots/start-page.png)

![Data acquisition](docs/assets/screenshots/data-acquisition.png)

![Processing setup](docs/assets/screenshots/processing-setup.png)

更多页面截图见 [完整中文手册](docs/USER_GUIDE.md)。

## 核心功能

- 项目制工作区：每个项目保存下载数据、处理工作目录、日志、quicklook 和 `project.pilot`。
- 专用项目文件：`.pilot` 是 InSAR-PILOT 的项目后缀，内部仍采用可审计的 JSON 结构；旧版 `insar_pilot_project.json` 仍可读取。
- Data Acquisition：Earthdata 账户检查、ASF Sentinel-1 SLC 查询、场景选择、SLC/EOF 下载、地图与场景表查看。
- Processing Setup：数据源、EOF、DEM、AOI/BBox、IW、参考影像、处理参数、preflight 和命令预览集中配置。
- Run Executor：发现并执行 `run_files/run_*`，支持 next/selected/remaining 执行，显示 step/subcommand 状态、日志和 exit code。
- Results Quicklook：扫描输出结果，预览或导出 SLC、干涉图和 overlay quicklook。
- 桌面适配：启动器自动选择 WSL2/WSLg 或 Ubuntu Desktop 的 Qt 显示后端，并支持 WebEngine 地图 fallback。

## 安装与启动

推荐使用 conda 环境：

```bash
git clone https://github.com/WU-Pengzhan/InSAR-PILOT.git
cd InSAR-PILOT

conda env create -f environment.yml
conda activate insar

pip install .
insar-pilot
```

开发模式：

```bash
pip install -e .[dev]
insar-pilot
```

## 典型工作流

1. New Project 或 Open Project，选择一个项目文件夹。
2. 在 Data 页面设置时间、AOI、轨道方向、极化方式并查询 Sentinel-1 场景。
3. 选择场景后下载 SLC ZIP 和 EOF 轨道文件。
4. 在 Setup 页面选择 DEM、BBox/IW 和处理参数，运行 Validate/Prepare 与 Preflight。
5. 生成官方处理命令和 `run_files`。
6. 在 Run 页面执行 run_files，并观察日志、子命令状态和失败信息。
7. 在 Results 页面扫描输出并生成 quicklook。

项目文件夹默认结构：

```text
project_root/
  project.pilot
  data/
    SLC/
    Orbit/
    DEM/
  processing/work/
  outputs/quicklooks/
  logs/
  .insar_pilot/cache/
```

## 无界面 / CLI 用法

在没有图形界面的服务器上，可用 `insar-pilot-cli` 直接驱动同一套项目状态（`project.pilot` 与 `logs/` 完全兼容 GUI，可互换打开）。

```bash
# 1. 创建标准项目目录与 project.pilot
insar-pilot-cli init /data/aoi_stack --name aoi_stack

# 2. 预览生成命令（不执行）；确认无误后执行生成并同步 run_files
insar-pilot-cli generate /data/aoi_stack --dry-run
insar-pilot-cli generate /data/aoi_stack

# 3. 顺序执行 run 步骤（首个非零退出即停止）；也可选步骤区间
insar-pilot-cli run /data/aoi_stack
insar-pilot-cli run /data/aoi_stack --steps 2-5

# 4. 查看各步骤状态与日志路径
insar-pilot-cli status /data/aoi_stack
```

退出码：`0` 成功，`1` 命令执行失败，`2` 用法或配置错误。数据/DEM/AOI 的准备目前仍在 GUI 中完成；CLI 侧重生成、执行与状态查询。

## 平台与运行环境

- Ubuntu Desktop 或 WSL2/WSLg。
- Python 3.10-3.12。
- conda 环境默认名：`insar`。
- `environment.yml` 安装 GUI 依赖、ISCE2、GDAL、aria2、sentineleof、asf-search 等运行组件；SLC 下载依赖 aria2c 的分片续传能力。
- 可选 WebEngine 地图支持：`pip install '.[map]'`。

如果遇到 Qt、地图、DEM 或 run_files 执行问题，请先看 [docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md)。

## 测试

当前开发测试固定在已有 `insar` 环境中运行：

```bash
conda run -n insar env PYTHONPATH=src QT_QPA_PLATFORM=offscreen pytest -q
```

## 许可证

本项目使用 [Apache-2.0](LICENSE) 许可证。
