# 端到端教程

本教程走一遍完整流程：**建项目 → 准备数据 → 配置工作流 → 生成 run_files → 执行 → 看结果**，同时给出 **GUI** 与 **CLI** 两条路径。

!!! warning "前置条件（诚实说明）"
    - 需要按[安装](installation.md)完成的 conda `insar` 环境，其中含 ISCE2/GDAL/aria2/snaphu/`stackSentinel.py`。这些**无法** pip 安装，也不会在测试环境中出现——只有真正处理时才需要。
    - 数据下载需要可用的 [Earthdata](https://urs.earthdata.nasa.gov/) 账户。
    - 请先用**小范围样例**验证整条链路，再进入生产。
    - 数据/DEM/AOI 的准备目前只在 GUI 完成；CLI 负责生成、执行与状态查询。

## 0. 项目布局

无论走哪条路径，项目文件夹结构一致：

```text
project_root/
  project.pilot          # 项目状态（JSON 内核）
  data/
    SLC/                 # Sentinel-1 SLC ZIP
    Orbit/               # EOF 轨道文件
    DEM/                 # DEM
  processing/work/       # ISCE2 工作目录（run_files/configs 在此生成）
  outputs/quicklooks/
  logs/                  # 生成/执行/可视化日志
  .insar_pilot/cache/
```

`project.pilot` 与 `logs/` 在 GUI 与 CLI 之间**完全兼容**，可随时互换打开。

---

## 路径 A：GUI

### A1. 建项目

启动后 New Project，选一个空文件夹。InSAR-PILOT 会创建上面的标准布局。

```bash
conda activate insar
insar-pilot
```

### A2. 准备数据（Data Acquisition）

![Data acquisition](assets/screenshots/data-acquisition.png)

1. 先**测试 Earthdata/ASF 账户**。
2. 设置起止日期、AOI、轨道方向、相对轨道号、极化方式。
3. 查询 ASF Sentinel-1 SLC 场景，在地图/表格中检查 footprint 与元数据。
4. 选择场景，下载 **SLC ZIP** 与 **EOF 轨道文件**（SLC 下载走 `aria2c` 分片续传）。
5. 把下载目录导入到 Setup 的数据源字段。

> 如果你已有现成的 SLC/EOF/DEM，可跳过下载，直接在 Setup 里把 SLC 目录、EOF 目录、DEM 路径指向已有文件。

### A3. 配置工作流（Processing Setup）

![Processing setup](assets/screenshots/processing-setup.png)

1. **校验环境**：确认 ISCE2/GDAL/snaphu/stack 工具在当前运行时可发现。
2. 确认 SLC 输入目录、EOF 目录、**DEM 路径**、处理工作目录。
3. 准备 ZIP/SAFE 输入清单。
4. 设置 AOI/BBox、IW swaths、参考影像、极化。
5. 配置 workflow、coregistration、looks、parallelism 等参数。
6. 运行 **Preflight**：检查路径、权限、缺失输入、DEM/EOF、以及已存在的 `run_files`/`configs` 冲突。
7. **预览并生成**官方 `stackSentinel.py` 命令与 `run_files`。

!!! note
    生成步骤**拒绝覆盖**已存在的 `run_files`/`configs`。需要重来时，先手动清理 `processing/work/` 下这两个目录。

### A4. 执行（Run Executor）

- `Run Next Step` 执行下一个 pending/failed/cancelled step。
- `Run Selected Step` 重跑选中 step。
- `Run Remaining Steps` 连续跑完剩余 step。
- `Stop` 请求停止当前执行。

每个 step 与 subcommand 记录状态、日志路径、exit code。**失败即停**：先看对应 subcommand 日志，修正后用 selected/next 续跑，无需从头。

### A5. 看结果（Results Quicklook）

![Results quicklook](assets/screenshots/results-quicklook.png)

扫描输出目录，浏览 SLC / 干涉图 / merged products / quicklook，生成预览并导出 BMP quicklook。

---

## 路径 B：CLI（无界面服务器）

一种常见分工：先在 GUI 里下载数据并准备好 `data/SLC`、`data/Orbit`、`data/DEM`，把项目文件夹搬到服务器，再用 CLI 批量生成与执行。

```bash
conda activate insar

# 1. 建项目（若已有项目文件夹可跳过）
insar-pilot-cli init /data/aoi_stack --name aoi_stack

# 2. 预览生成命令（不执行），确认无误后正式生成并同步 run_files
insar-pilot-cli generate /data/aoi_stack --dry-run
insar-pilot-cli generate /data/aoi_stack

# 3. 顺序执行（首个非零退出即停止）；也可只跑区间
insar-pilot-cli run /data/aoi_stack
insar-pilot-cli run /data/aoi_stack --steps 2-5

# 4. 查看各步骤状态与日志路径
insar-pilot-cli status /data/aoi_stack
```

退出码：`0` 成功，`1` 命令执行失败，`2` 用法/配置错误。每步状态写回 `project.pilot`，所以中途可随时切回 GUI 用 Run 页面接续。

各命令的完整参数见[命令行 CLI](cli.md)。

---

## 出问题了？

先看[故障排查](troubleshooting.md)：涵盖 Qt 显示后端、地图卡顿、环境校验、ASF 下载、DEM 准备、`run_files` 执行失败以及日志位置。
