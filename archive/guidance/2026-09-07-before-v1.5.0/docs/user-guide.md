# InSAR-PILOT 用户手册

> **Web 预览版的退出方式：** 关闭浏览器后后台仍会运行。请点击右上角“退出应用”；有任务时先进入任务页暂停或取消，待进程退出后再退出应用。终端可使用 `insar-pilot-web --status` 查询、`insar-pilot-web --stop` 在空闲时退出。重新启动使用 `insar-pilot-web`。自定义状态目录需使用相同的 `--state` 参数。下文为保留的 legacy 桌面版使用说明。


<p align="center">
  <img src="assets/branding/logo.png" width="640" alt="InSAR-PILOT logo">
</p>

[返回首页](index.md) | [English Guide](en/user-guide.md) | [故障排查](troubleshooting.md)

## 1. 软件定位

**InSAR-PILOT** 是 **InSAR Processing Interface and Lightweight Orchestration Toolkit** 的缩写，中文可理解为“面向 InSAR 处理的轻量级图形界面与流程编排工具”。

它是一个面向 Ubuntu Desktop 和 WSL2/WSLg 的开源桌面处理工作台，以项目文件夹为单位，组织 SAR 数据下载、处理参数设置、官方处理链生成、run_files 执行监控和结果 quicklook 预览。

v1.2.0 的正式产品范围是 Sentinel-1 与 ISCE2 官方 TOPS Stack 处理流程。

v1.0.0 是首个正式发布版。建议先使用小范围样例项目验证运行环境、下载链路和处理结果，再进入正式生产流程。

## 2. 启动页与项目制

![Start page](assets/screenshots/start-page.png)

启动后先创建或打开项目。正式处理应始终绑定一个项目文件夹，便于保存数据、日志、状态和输出。

默认项目结构：

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

`project.pilot` 保存 GUI 状态、下载参数、处理设置、执行状态和 quicklook 配置。该文件使用 InSAR-PILOT 专用后缀，内部仍是 JSON，便于审计和排查。旧版 `insar_pilot_project.json` 项目文件仍可加载。底层处理结果仍保存在处理工作目录中的标准输出文件夹内。

## 3. Data Acquisition

![Data acquisition](assets/screenshots/data-acquisition.png)

Data 页面负责 Sentinel-1 数据准备：

- 填写或从 `~/.netrc` 加载 Earthdata/ASF 账户；连接测试仅用于提前诊断，完整凭据可直接下载。
- 输入日期、AOI、轨道方向、相对轨道号和极化方式。
- 查询 ASF Sentinel-1 SLC 场景。
- 在地图和表格中检查 footprint 与元数据。
- 选择场景并下载 SLC ZIP 和 EOF 轨道文件。
- 将下载目录导入到 Setup 的数据源字段。

建议先测试账户，再设置检索条件。搜索结果不会因为下载进度刷新而重置地图视图；日志只在用户停留底部时自动滚动。

KML AOI 支持 `Polygon`、`LineString` 和 `Point`。ASF 每次只接受一个检索几何；当 KML 包含多条线时，软件使用覆盖距离最长的主线检索，同时在地图预览和范围计算中保留全部线段。

### DEM 下载来源

- COP30 不需要 OpenTopography key。软件按计划范围解析 1° COG 瓦片，从 AWS Open Data 使用 8 路可续传 Range 下载到 `DEM/cache/cop30/`，随后由 GDAL 裁剪/拼接为一个 AOI GeoTIFF。同一下载工作区再次使用该瓦片时直接命中缓存。
- AW3D30_E 仍使用 OpenTopography，必须先验证 API key。
- 两种 DEM 的高程基准不同：COP30 为 EGM2008，AW3D30_E 为 WGS84 椭球高。不要仅按文件扩展名推断高程基准。
- 默认网络模式为 `direct`，明确忽略 WSL 的代理环境变量；只有选择 `environment` 时才继承代理。

## 4. Processing Setup

![Processing setup](assets/screenshots/processing-setup.png)

Setup 页面集中完成处理前配置：

- 检查当前启动环境中的 ISCE2/GDAL/snaphu/stack 工具。
- 选择或确认 Sentinel-1 输入目录、EOF 目录、DEM 路径和处理工作目录。
- 准备 ZIP/SAFE 输入清单。
- 设置 AOI/BBox、IW swaths、参考影像和极化参数。
- 配置 workflow、coregistration、looks、parallelism 等处理参数。
- 运行 Preflight，检查路径、权限、输入缺失、DEM/EOF、已有 run_files/configs 冲突。
- 预览并生成官方处理命令和 `run_files`。

主界面尽量展示操作人员需要的内容；完整路径、命令和诊断信息保留在 Technical Details 或日志中。

## 5. Run Executor

![Run executor](assets/screenshots/run-executor.png)

Run 页面用于执行和恢复处理：

- `Run Next Step` 执行下一个 pending/failed/cancelled step。
- `Run Selected Step` 重新执行选中的 step。
- `Run Remaining Steps` 连续执行剩余 step。
- `Stop` 请求停止当前执行。

每个 step 和 subcommand 会记录状态、日志路径、exit code 和错误信息。失败后建议先查看 subcommand log，再修正输入或环境，然后使用 selected/next 继续。

## 6. Results Quicklook

![Results quicklook](assets/screenshots/results-quicklook.png)

Results 页面使用全宽产品工作台，只负责核心雷达产品浏览和可视化：

- 自动归并原始数据、XML、VRT 和 full VRT，在可搜索目录中显示 SLC、滤波/未滤波 INT、相干系数和解缠相位；几何与中间文件通过“打开其他文件”访问。
- 选择 INT 时默认按参考日期匹配 merged SLC 并生成 overlay；标准 overlay 使用同一配准网格的 SLC
  强度作为明暗、INT 的 `arg(INT)` 作为相位颜色，并以 `abs(INT) > 0`
  限制有效区；SLC 留空时使用 `abs(INT)` 作为亮度。
- 参数变化后由用户点击“预览”再生成，避免全分辨率产品被反复自动计算；预览支持 Ctrl+滚轮缩放、滚轮浏览、适应窗口和 100% 像素显示。
- 相干系数使用 0–1 Viridis 色标；解缠相位默认使用有效像素 P2–P98 连续色标。
- 默认裁剪到相位产品的有效数据外包范围，不额外压缩生成影像；导出支持无损 PNG 和 BMP，并生成同名 JSON 参数文件。
- 日志控制台启动时保持隐藏，仅在用户通过“视图”菜单打开时显示。

该页面不承担流程状态管理；流程状态以项目文件、Run 页面和日志为准。

## 7. ISCE2 调用关系

InSAR-PILOT 当前的 Sentinel-1 处理能力建立在 [ISCE2](https://github.com/isce-framework/isce2) 及其官方 [stack processors / TOPS stack](https://github.com/isce-framework/isce2/blob/main/contrib/stack/README.md) 之上。ISCE2 是开源 InSAR 科学计算环境，InSAR-PILOT 通过桌面界面、项目制工作区和执行监控把它的 Sentinel-1 TOPS 工作流组织得更容易使用。

> 致谢与边界：InSAR-PILOT 不是 ISCE2 官方项目，不修改 ISCE2 算法，也不重新发布 ISCE2 的处理结果解释。本项目尊重并依赖 ISCE2 开源工作，目标是为用户提供更清晰的输入准备、命令生成、run_files 执行和日志检查界面。

GUI 负责：

- 收集并保存参数。
- 准备输入目录与 DEM。
- 构造官方 `stackSentinel.py` 命令。
- 解析生成的 `run_files/run_*`。
- 调用 shell 执行 run files。
- 展示日志、状态、exit code 和输出结果。

GUI 不修改 ISCE2 算法，不伪装处理结果，也不把 run_files 隐藏成黑盒。

## 8. 安装、启动与测试

安装：

```bash
bash install.sh
conda activate insar
insar-pilot
```

测试：

```bash
conda run -n insar env PYTHONPATH=src QT_QPA_PLATFORM=offscreen pytest -q
```

## 9. 无界面 / CLI

在没有图形界面的服务器上，`insar-pilot-cli` 复用与 GUI 相同的 Qt-free 服务层，
`project.pilot` 与 `logs/` 输出在两个前端之间完全兼容、可互换打开。四个子命令：

- `init <dir> [--name NAME]` — 创建标准项目目录与 `project.pilot`。
- `generate <project_dir> [--dry-run]` — 构造 `stackSentinel.py` 命令，拒绝覆盖已存在的
  `run_files`/`configs`，执行生成并同步 run 步骤；`--dry-run` 仅打印命令后退出。
- `run <project_dir> [--steps A[-B]] [--dry-run]` — 按顺序执行待运行步骤，首个非零退出即停止，
  每步状态写回 `project.pilot`；`--steps` 选择 1 基编号的单步或区间。
- `status <project_dir>` — 打印步骤/状态/日志的紧凑表格。

退出码：`0` 成功，`1` 命令执行失败，`2` 用法或配置错误。数据/DEM/AOI 的准备目前仍在 GUI 中完成。

```bash
insar-pilot-cli init /data/aoi_stack --name aoi_stack
insar-pilot-cli generate /data/aoi_stack --dry-run
insar-pilot-cli generate /data/aoi_stack
insar-pilot-cli run /data/aoi_stack --steps 2-5
insar-pilot-cli status /data/aoi_stack
```
