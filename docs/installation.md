# 安装

InSAR-PILOT 面向 **Ubuntu Desktop** 与 **WSL2/WSLg**，支持 Python 3.10–3.12。运行真正的处理需要 ISCE2/GDAL/aria2 等组件，这些**无法通过 pip/uv 安装**，必须使用 conda 环境。

## 类比与要点

把 InSAR-PILOT 想成“驾驶舱”，ISCE2 是“发动机”：驾驶舱本身很轻（只需 PySide6 与标准库），但要真正起飞，得先装好发动机（conda 里的 ISCE2 运行时）。因此安装分两种场景：

- **只做开发/测试**：一个 uv 管理的轻量虚拟环境即可，不需要 ISCE2。
- **运行 GUI 处理**：需要 `environment.yml` 提供的完整 conda 运行时。

## 运行时安装（conda，推荐）

```bash
git clone https://github.com/WU-Pengzhan/InSAR-PILOT.git
cd InSAR-PILOT

conda env create -f environment.yml   # 默认环境名 insar
conda activate insar

pip install .
insar-pilot
```

`environment.yml` 会安装 GUI 依赖、ISCE2、GDAL、aria2、sentineleof、asf-search 等运行组件。SLC 下载依赖 `aria2c` 的分片续传能力。

可选 WebEngine 地图支持：

```bash
pip install '.[map]'
```

!!! note "环境即运行时"
    InSAR-PILOT 从**启动它的进程**探测运行时（ISCE2/GDAL/snaphu/stack 工具）。务必先 `conda activate insar` 再启动 `insar-pilot`，否则 Setup 页面的环境校验会失败。

## 开发环境安装（uv，无需 ISCE2）

日常开发只需仓库自带的 uv 虚拟环境，它提供 PySide6 与标准库，足够跑测试与 lint：

```bash
uv sync --extra dev
```

测试与 lint 详见 [贡献指南](https://github.com/WU-Pengzhan/InSAR-PILOT/blob/main/CONTRIBUTING.md)：

```bash
# 全量测试（无头 Qt，需 offscreen 平台插件）
QT_QPA_PLATFORM=offscreen uv run pytest -q

# Lint
uv run ruff check src tests
```

## WSL2 / Ubuntu 说明

- 启动器会自动为 WSL2/WSLg 或原生 Ubuntu 选择合适的 Qt 显示后端（`xcb`/`wayland`）；用户显式设置的 `QT_QPA_PLATFORM` 始终优先。
- 若 Qt 报缺少 xcb 运行库：

    ```bash
    sudo apt install -y libxcb-cursor0 libxcb-xinerama0 libxkbcommon-x11-0
    ```

- 更多显示后端、地图卡顿、DEM、run_files 问题见 [故障排查](troubleshooting.md)。

## 下一步

- 想尽快看到界面跑起来：[快速开始](quickstart.md)。
- 想走完整流程（含数据下载与出结果）：[端到端教程](tutorial.md)。
