# 命令行 CLI

旧 CLI 用于 ProjectStore 工程，Web 使用独立存储与 Job Engine。请将旧工程导入新的 Web 工程，不要在同一目录交替使用 CLI 与 Web 执行。以下命令保留旧格式兼容。

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

## 兼容边界

执行需要有效输入与科学环境。已有 run_files/configs 不自动覆盖，重跑使用新隔离目录。Web 导入保留来源，不搬迁旧目录。
