# ISCE2 Sentinel-1 TOPS GUI（简体中文手册）

## 1. 概览

本项目是面向 Ubuntu/WSL 的 ISCE2 `topsStack` 桌面编排工具。  
它调用官方 ISCE2 脚本与 `run_files`，不重写 ISCE 处理内核。

当前 Stage 2 工作流页面：

1. `Data Sources`
2. `AOI + BBox + IW`
3. `Processing Plan`
4. `Run Monitor`
5. `Results & Visualization`

## 2. 环境要求

- Ubuntu（推荐 WSL）
- conda 环境（文档默认名：`isce-master`）
- `environment.yml` 已包含 ISCE2（`isce2` 依赖）
- 运行 shell 可找到 ISCE/GDAL 等命令

环境可在 `Data Sources` 页面中直接校验。

## 3. 安装与启动

### 3.1 克隆仓库

```bash
git clone https://github.com/WU-Pengzhan/isce-master.git
cd isce-master
```

也可以直接下载 GitHub Release 的源码压缩包并解压，然后在解压后的项目根目录执行同样步骤。

### 3.2 创建 conda 环境

```bash
conda env create -f environment.yml
conda activate isce-master
```

### 3.3 安装 GUI

```bash
pip install .
```

### 3.4 启动

```bash
isce2-gui
```

或：

```bash
python -m isce2_gui
```

## 4. 推荐使用流程

### 4.1 Data Sources

- 设置 shell/conda/ISCE root（运行环境折叠区）
- 选择数据目录（ZIP/SAFE）、Orbit、DEM、可选 AUX、工作目录
- 如果 DEM 是 GeoTIFF，选择高程基准（`EGM96` 或 `WGS84`）
- 点击 `Validate & Prepare Data`

### 4.2 AOI + BBox + IW

- 可选导入 AOI 文件（`.kml` / `.shp`）自动回填 ISCE bbox
- 设置 bbox（SNWE 小数度）或开启 common overlap
- 选择 IW 条带
- 点击 `Recommend IW` 和 `Verify Geometry`
- Verify 图层包含：
  - AOI
  - ISCE bbox
  - IW 覆盖范围
  - 自动命中的 burst 覆盖范围
  - DEM 覆盖框

### 4.3 Processing Plan

- 设置 workflow/coreg/connectivity/looks/并行/参考日期
- 生成官方 stack 命令与 `run_files`

### 4.4 Run Monitor

- 用 `Run Next Step` / `Run Selected Step` / `Run Remaining Steps` 执行
- 查看步骤与子命令状态、退出码和日志

### 4.5 Results & Visualization

- 浏览自动发现的输出目录
- 预览/导出 quicklook：
  - SLC
  - 干涉相位
  - SLC 背景 + 相位叠加

## 5. 项目元数据目录

工作目录 `<work_dir>` 下 GUI 元数据位于：

- `<work_dir>/.iscegui/project.json`
- `<work_dir>/.iscegui/logs/`
- `<work_dir>/.iscegui/inputs/`
- `<work_dir>/.iscegui/dem_import/`
- `<work_dir>/.iscegui/visualize/`

ISCE 原生输出仍保持在标准目录（如 `run_files/`、`reference/`、`coreg_secondarys/`、`merged/` 等）。

## 6. 关键处理说明

- bbox 仅支持 SNWE 矩形。
- 空 bbox（common overlap）不是最终硬裁剪。
- GeoTIFF 导入路径要求地理坐标 WGS84 网格。
- 高程基准转换由用户显式指定（`EGM96` 或 `WGS84`）。
- burst 级能力当前用于 verify 提示，实际处理参数仍是 swath 级。

## 7. 常用成果与排障位置

- 干涉与相干：`merged/interferograms/`
- 合并 SLC：`merged/SLC/`
- quicklook 导出：`.iscegui/visualize/`
- 运行日志：`.iscegui/logs/`

## 8. WSL 说明

- 在 WSL/WSLg 环境下，为避免下拉/弹窗异常，应用会在未显式设置时默认使用 `QT_QPA_PLATFORM=xcb`。
- 也可手动覆盖：

```bash
QT_QPA_PLATFORM=wayland isce2-gui
```

更多问题见 [docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md)。
