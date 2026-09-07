# 命令行 CLI

在没有图形界面的服务器上，用 `insar-pilot-cli` 直接驱动同一套项目状态。CLI 复用与 GUI 完全相同的 Qt-free 服务层，`project.pilot` 与 `logs/` 输出在两个前端之间**完全兼容、可互换打开**——CLI 生成的项目可以在 GUI 里接着跑，反之亦然。

## 四个子命令

| 命令 | 作用 |
| --- | --- |
| `init <dir> [--name NAME]` | 创建标准项目目录与 `project.pilot`；`--name` 默认取目录名 |
| `generate <project_dir> [--dry-run]` | 构造 `stackSentinel.py` 命令，拒绝覆盖已存在的 `run_files`/`configs`，执行生成并同步 run 步骤；`--dry-run` 仅打印命令后退出 |
| `run <project_dir> [--steps A[-B]] [--dry-run]` | 顺序执行待运行步骤，首个非零退出即停止，每步状态写回 `project.pilot`；`--steps` 选择 1 基编号的单步或区间 |
| `status <project_dir>` | 打印步骤 / 状态 / 日志的紧凑表格 |

## 典型流程

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

## 退出码

| 码 | 含义 |
| --- | --- |
| `0` | 成功 |
| `1` | 某个 shell 命令执行失败 |
| `2` | 用法或配置错误（参数错误、项目缺失/损坏、生成被拒绝） |

## 边界与互操作

- 数据下载、DEM 与 AOI 的准备目前仍在 **GUI** 中完成；CLI 侧重**生成、执行与状态查询**。一种常见分工：在 GUI 里下载数据并准备好 SLC/EOF/DEM，再把项目搬到无界面服务器上用 CLI 批量执行。
- `run` 的每步状态、日志命名与批次拆分逻辑与 GUI 一致，因此中途可随时切回 GUI 用 Run 页面接续。
- `generate` 与 GUI 一样，**不会**覆盖已存在的 `run_files`/`configs`——需要重来时先自行清理这些目录。

完整界面说明见[完整手册](user-guide.md)。
