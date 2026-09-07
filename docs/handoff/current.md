# 当前交接

更新：2026-09-07。最新任务为 [1.5.0 文档重构、残余清理与发行](records/2026-09-07-v1.5.0-release.md)。

## 当前基线

- Web 唯一、Sentinel 优先、单工程 Profile、五页职责不变。P01 已实现，P02—P05 专业页面待设计。
- `insar-pilot` 和 `python -m insar_pilot` 转为 Web；保留 `insar-pilot-web`。Qt 专属代码/依赖已清理，旧 CLI 与科学后端保留。
- README 中英面向产品介绍，安装、使用、维护、架构与交接分层；旧指导有摘要归档。
- 工程显式打开/关闭，新工程 data/processing/products，旧布局不移动；.pilot 不等于完整数据备份。
- P01 冻结获取目标、完整校验与来源复用；后台任务跨页面/浏览器保留。
- 同一时刻一个窗口进入，其余等待，异常断开约 15 秒释放；运行环境只检测与提示。

## 下一步

先核对[本轮记录](records/2026-09-07-v1.5.0-release.md)的最终测试与发布结果，再按用户指令进入 [P02 卡](pages/p02-data-preparation.md)。真实下载长时吞吐独立验收；D01 产品合同仍未决。

## 本机定位信息

- 仓库：`/home/griffin/projects/insar-pilot`，命令在 WSL Ubuntu 中执行。
- Web Python：`/home/griffin/.local/share/insar-pilot/web-venv/bin/python`。
- 科学/旧后端环境：`/home/griffin/miniconda3/envs/insar/bin/python`，只用于相关后端测试。
- Node：`/home/griffin/.local/share/insar-pilot/dev-tools/node-v22.14.0-linux-x64/bin/node`。
- 正式服务状态：`~/.local/state/insar-pilot`；入口端口 8765。任务开始实测 RUNNING，0 下载/处理/worker；结束状态见最新记录，不沿用历史瞬时数。
- 任务开始 Git HEAD `5a6df49`，工作树干净；当前 Git 状态须实时查询。

不要将永久环境放到临时目录，不输出会话凭据，不修改用户科学输入与黄金数据。
