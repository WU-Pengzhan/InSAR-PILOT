# 安装与当前兼容边界

当前 Web 产品的启动方法见 [README](https://github.com/WU-Pengzhan/InSAR-PILOT#readme)，科学环境采用[独立运行时合同](architecture/runtime-support.md)。
Web 启动成功不代表 ISCE2/ISCE3 已安装。顶部“运行环境”显示实际检测结果，环境由用户管理，软件不区分包管理类型或自动安装。

以下为原 Qt/ISCE2 安装路径的历史说明，保留用于已有用户维护；其中“必须 Conda”“必须激活启动”“WSLg/Qt”不构成新版 Web 规范，也不覆盖 ISCE3。

## 历史安装说明

InSAR-PILOT 面向 **Ubuntu Desktop** 与 **WSL2/WSLg**。Python 包支持 3.10–3.12；完整处理环境当前固定使用 Python 3.10，以匹配 ISCE2/GDAL。运行真正的处理需要 ISCE2/GDAL/aria2 等组件，这些**无法仅通过 pip/uv 安装**，必须使用 conda 环境。

## 类比与要点

把 InSAR-PILOT 想成“驾驶舱”，ISCE2 是“发动机”：驾驶舱本身很轻（只需 PySide6 与标准库），但要真正起飞，得先装好发动机（conda 里的 ISCE2 运行时）。因此安装分两种场景：

- **只做开发/测试**：一个 uv 管理的轻量虚拟环境即可，不需要 ISCE2。
- **运行 GUI 处理**：需要 `environment.yml` 提供的完整 conda 运行时。

## 一键运行时安装（推荐）

```bash
# 下载并解压 GitHub Release 源码 ZIP 后：
cd InSAR-PILOT
bash install.sh
conda activate insar
insar-pilot
```

用户只需要已初始化的 Conda 和能够访问 `conda-forge` 的网络，不要求预装 ISCE2、GDAL、Git 或系统 Python 包。`install.sh` 会创建或更新默认的 `insar` 环境，安装本软件和完整运行时并执行验证。使用 `bash install.sh my-insar` 可以指定环境名。

`environment.yml` 会安装 GUI、QtWebEngine 地图、ISCE2 2.6.5、GDAL、aria2、sentineleof、asf-search 和 SNAPHU。SLC 和 DEM 下载依赖 `aria2c` 的分片续传能力。

!!! note "环境即运行时"
    InSAR-PILOT 从**启动它的进程**探测运行时（ISCE2/GDAL/snaphu/stack 工具）。请先激活安装 InSAR-PILOT 的环境再启动；这里的 `insar` 只是文档示例名称。项目文件不会切换 Conda 环境。

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
