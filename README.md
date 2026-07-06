# InSAR-PILOT

<p align="center">
  <img src="docs/assets/branding/logo.png" width="640" alt="InSAR-PILOT logo">
</p>

**InSAR-PILOT** 是 **InSAR Processing Interface and Lightweight Orchestration Toolkit** 的缩写，中文可理解为“面向 InSAR 处理的轻量级图形界面与流程编排工具”。

**副标题：Open Desktop Workbench for Guided SAR/InSAR Processing**

[English](README_EN.md) | [完整中文手册](docs/USER_GUIDE.md) | [故障排查](docs/TROUBLESHOOTING.md)

InSAR-PILOT 是一个开源、窗口化、轻量级的 SAR/InSAR 桌面处理工作台。它以项目文件夹为核心，帮助用户完成 SAR 数据检索与下载、轨道与 DEM 准备、处理参数配置、处理链生成、任务执行监控和结果 quicklook 预览。

当前版本主要面向 Sentinel-1 与 ISCE2 官方处理流程，后续目标是逐步接入更多 SAR 载荷和时序 InSAR 处理能力，包括 SBAS、StaMPS 等流程。

> 阶段说明：当前版本仍处于测试阶段，建议先在小范围样例项目中验证环境、数据下载和处理结果，再用于正式生产流程。

## 界面预览

![Start page](docs/assets/screenshots/start-page.png)

![Data acquisition](docs/assets/screenshots/data-acquisition.png)

![Processing setup](docs/assets/screenshots/processing-setup.png)

更多页面截图见 [完整中文手册](docs/USER_GUIDE.md)。

## GitHub 品牌资源

- 横向 logo：`docs/assets/branding/logo.png`
- 仓库头像 / 项目头像：`docs/assets/branding/github-avatar.png`
- Repository social preview：`docs/assets/branding/github-social-preview.png`

GitHub 不会自动从仓库文件读取头像或 social preview。发布后需要在 GitHub Settings 页面手动上传对应图片。

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
