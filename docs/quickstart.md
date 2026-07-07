# 快速开始（GUI）

本页给出图形界面的最短上手路径。假设你已按[安装](installation.md)完成 conda 环境并可启动 `insar-pilot`，且拥有可用的 [Earthdata](https://urs.earthdata.nasa.gov/) 账户。

## 启动

```bash
conda activate insar
insar-pilot
```

## 四个页面，一条主线

InSAR-PILOT 的界面按处理顺序分为四页，从左到右推进即可：

1. **新建/打开项目** — 选择一个项目文件夹。所有数据、日志、状态、输出都绑定到它。
2. **Data Acquisition** — 测试 Earthdata 账户 → 设置日期/AOI/轨道方向/极化 → 查询 Sentinel-1 场景 → 选择并下载 SLC ZIP 与 EOF 轨道文件。
3. **Processing Setup** — 校验环境 → 确认 SLC/EOF/DEM 与工作目录 → 设置 AOI/BBox、IW、参考影像与处理参数 → 运行 Preflight → 预览并生成 `stackSentinel.py` 命令与 `run_files`。
4. **Run Executor** — 执行 `run_files/run_*`，观察 step/subcommand 状态、日志与 exit code。
5. **Results Quicklook** — 扫描输出，预览/导出 SLC、干涉图与 overlay quicklook。

![Processing setup](assets/screenshots/processing-setup.png)

## 关键提示

- 建议先用**小范围样例**验证运行环境、下载链路和处理结果，再进入正式生产。
- 失败后先看对应 subcommand 的日志，修正输入或环境，再用 `Run Selected Step` / `Run Next Step` 续跑，无需从头重来。
- 生成步骤**拒绝覆盖**已存在的 `run_files`/`configs` 目录，避免误删已有进度。

## 下一步

- 每个页面的字段与行为：[完整手册](user-guide.md)。
- 从零到出结果的完整走查（含 CLI 路径）：[端到端教程](tutorial.md)。
- 无图形界面的服务器：[命令行 CLI](cli.md)。
