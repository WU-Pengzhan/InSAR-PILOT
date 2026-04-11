# ISCE2 Sentinel-1 TOPS GUI（简体中文手册）

## 1. 项目概览

本 GUI 是面向 Ubuntu/WSL 的本地 ISCE2 `topsStack` 工作流编排工具。
它负责输入准备、`run_files` 生成、分步执行与结果查看，不重写 ISCE 内核算法。

核心原则：

- 优先使用官方 `stackSentinel.py` 与 `run_files`。
- 尽量保持 ISCE 原生目录结构与文件命名。
- 失败必须可定位，日志和步骤状态要清晰。

## 2. 当前可用能力

- 本地环境检测（`python`、ISCE 脚本、GDAL 辅助脚本、`snaphu`）。
- 两阶段输入流程：
1. 数据预检：SLC/Orbit/DEM 与可选 ZIP 解压。
2. 处理规划：bbox、workflow、coreg、looks、`num_proc` 等。
- GeoTIFF DEM 导入为 ISCE 可用 DEM（输出到 `.iscegui/dem_import/`）。
- GeoTIFF 垂直基准由用户明确选择：
  - `EGM96 geoid -> convert to WGS84`
  - `Already WGS84 ellipsoid`
- 工作流执行方式：
  - `Run Next Step`
  - `Run Selected Step`
  - `Run Remaining Steps`
- 可视化预览与导出：
  - SLC 灰度图
  - 干涉图彩色相位图
  - SLC 背景 + 干涉相位叠加图

## 3. 环境要求

- Ubuntu（推荐 WSL）。
- 已配置 ISCE2 相关依赖的 conda 环境（默认 `insar`）。
- 本地 ISCE2 根目录（默认 `/home/griffin/tools/isce2`）。

GUI 执行命令时会自动注入 ISCE 相关环境变量。

## 4. 安装与启动

```bash
source ~/.bashrc
conda activate insar
pip install -e .[dev]
isce2-gui
```

或：

```bash
python -m isce2_gui
```

## 5. 工程与元数据目录

设工作目录为 `<work_dir>`，GUI 元数据在：

- `<work_dir>/.iscegui/project.json`
- `<work_dir>/.iscegui/logs/`
- `<work_dir>/.iscegui/inputs/safe_inputs.txt`
- `<work_dir>/.iscegui/dem_import/`
- `<work_dir>/.iscegui/visualize/`

ISCE 原生结果仍在 `run_files/`、`configs/`、`reference/`、`coreg_secondarys/`、`merged/` 等标准目录中。

## 6. 推荐使用流程

### 6.1 首次新建项目（全流程）

1. 在 `1. Environment` 填写并检查 shell/conda/ISCE 路径，点击 `Validate Environment`。
2. 在 `2. Inputs -> Data Precheck` 设置：
   - Sentinel-1 输入目录（ZIP/SAFE）
   - Orbit 目录
   - DEM 路径
   - 若 DEM 为 `.tif/.tiff`，选择高程基准
   - 可选 AUX 目录
   - 工作目录
3. 点击 `Validate & Prepare Data`。
4. 在 `2. Inputs -> Processing Plan` 设置 bbox（SNWE 四框）或全部留空。
5. 在 `3. Execute` 点击 `Generate Workflow`。
6. 使用 `Run Next` 或 `Run Remaining` 执行。
7. 在 `4. Visualize` 预览/导出 BMP。

### 6.2 失败后恢复（继续已有项目）

1. 点击 `Open Project` 打开 `project.json`（或其父工作目录）。
2. 在 `Steps` 与 `Logs` 中定位失败步骤/子命令。
3. 选中目标步骤，点击 `Run Selected Step` 定点重跑。
4. 再用 `Run Next` 或 `Run Remaining` 继续。

## 7. 输入与处理关键说明

- bbox 仅支持 SNWE 矩形。
- bbox 全空表示“自动用共覆盖区域”，不是最终像素级硬裁剪。
- `num_proc` 同时用于 ISCE 并发参数与 run_file 子命令并发上限。
- GeoTIFF DEM 必须是地理坐标 WGS84 网格（类似 `EPSG:4326`）。
- 垂直基准不做“强推断”，以用户选择为准。

## 8. ISCE 典型步骤说明（`interferogram + NESD`）

实际步骤会随 workflow/选项变化。下表为常见 16 步流程。

| 步骤 | 主要操作 | 典型产物 | 常见失败信号 | 重跑建议 |
|---|---|---|---|---|
| `run_01_unpack_topo_reference` | 解包参考景并建立几何/topo | `reference/`、`geom_reference/` | DEM 警告、轨道缺失、解析错误 | 先修 DEM/Orbit/输入 |
| `run_02_unpack_secondary_slc` | 解包从景 SLC | `secondarys/` | SAFE/ZIP 缺失或解析失败 | 修正输入清单后重跑 |
| `run_03_average_baseline` | 计算基线信息 | `baselines/` | 参考/从景产物缺失 | 先确认 01/02 成功 |
| `run_04_extract_burst_overlaps` | 提取 overlap burst（ESD） | `reference/overlap/` | burst 不一致 | 检查 swath/bbox 一致性 |
| `run_05_overlap_geo2rdr` | overlap 区域 geo2rdr | overlap 几何文件 | 几何失败 | 检查 DEM 与几何链路 |
| `run_06_overlap_resample` | overlap 重采样 | overlap 配准产物 | 缺失 05 产物 | 先重跑 05 |
| `run_07_pairs_misreg` | 两两方位失配估计 | `misreg/azimuth/pairs/` | overlap XML 缺失、ESD 失败 | 多由前序 overlap/coreg 问题触发 |
| `run_08_timeseries_misreg` | 失配时序反演 | misreg 时序结果 | pair 为空、索引错误 | 先修复 07 |
| `run_09_fullBurst_geo2rdr` | 全 burst geo2rdr | 全 burst 几何产物 | DEM 覆盖边界不足 | 检查 DEM 覆盖余量 |
| `run_10_fullBurst_resample` | 全 burst 重采样/配准 | `coreg_secondarys/` | 缺失 geo2rdr 输入 | 先重跑 09 |
| `run_11_extract_stack_valid_region` | 计算堆栈共同有效区 | `stack/IW*.xml` | 各日期 burst 数不一致 | 检查从景一致性 |
| `run_12_merge_reference_secondary_slc` | 合并参考/从景 SLC | `merged/SLC/` | coreg 产物缺失 | 验证 10 成功 |
| `run_13_generate_burst_igram` | 生成 burst 干涉图 | burst 级干涉产物 | 输入链断裂 | 检查 10-12 |
| `run_14_merge_burst_igram` | 合并 burst 干涉图 | `merged/interferograms/*/fine.int*` | 合并维度不一致 | 检查 valid region |
| `run_15_filter_coherence` | 滤波与相干估计 | `filt_fine.int`、`fine.cor` | 滤波命令失败 | 先确认 `fine.int` |
| `run_16_unwrap` | 解缠（`snaphu`） | `filt_fine.unw*` | snaphu 缺失/配置错误 | 安装并检查 snaphu |

## 9. 用户最关注的成果文件

快速质检通常看：

- `merged/interferograms/*/fine.int*`
- `merged/interferograms/*/fine.cor*`
- `merged/interferograms/*/filt_fine.unw*`
- `4. Visualize` 导出的 quicklook BMP

后续分析常用：

- 解缠相位 `filt_fine.unw`
- 连通域 `filt_fine.unw.conncomp`
- 相干 `fine.cor`（或滤波后相干）

排障最关键：

- `.iscegui/logs/run_*.batch_*.log`
- `.iscegui/logs/run_*.cmd_*.log`
- `.iscegui/logs/stack_generate.log`

## 10. 可视化说明

- `Preview` 在缓存目录渲染并在 Preview 页展示。
- 若输入快照与参数不变，`Export BMP` 会直接复用最新 preview，不重复计算。
- 大图在 Preview 页支持滚动条完整查看。
- 边缘黑条常见于有效区掩膜与零填充边界，通常是显示层现象，不一定代表流程失败。

## 11. 常见问题

### DEM 覆盖不足但流程仍然跑通

- ISCE topo 常会警告 DEM 边界不足并继续使用交集区域。
- 这通常会优先影响边缘区域，中心区可能仍可用。
- 建议 DEM 覆盖范围大于整个 stack 外包框并留余量。

### 为什么 `Run Next` 不会重跑已成功步骤

- `Run Next` 只会选择 `pending/failed/cancelled`。
- 若要重跑某个 `success` 步骤，请用 `Run Selected Step`。

### 终端有 `libtinfo.so.6` 警告

- 多为 shell/conda 动态库混用产生的环境警告。
- 若命令执行和结果正常，可先按环境告警处理。

## 12. 常用命令

运行测试：

```bash
PYTHONPATH=src pytest -q
```

启动 GUI：

```bash
isce2-gui
```

快速查看日志目录：

```bash
ls -lah <work_dir>/.iscegui/logs
```

## 13. 当前阶段限制（Stage 1）

- 不支持远程下载数据。
- 仅支持 Sentinel-1 TOPS。
- 不支持多边形 AOI（仅 SNWE 矩形）。
- quicklook 以可读性和排障为主，不作为辐射定标产品。
