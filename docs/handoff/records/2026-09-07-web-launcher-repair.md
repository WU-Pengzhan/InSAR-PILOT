# 公共外壳｜修复 Web 启动解释器失效
日期：2026-09-07。
本次用户指令：运行 insar-pilot-web 报 exec Python not found，修复本机启动。
阶段：修复与定向验证。
任务卡：[公共入口](../pages/shell-project-entry.md)。
上一份：[工程与 P01 交付](2026-09-07-project-p01-release.md)，原样保留。

## 接受的决定与范围
- 仅修复本机 Web 环境和可复用启动入口，不推进 P02、不修改科学环境的包或科学参数。
- 正式环境、应用状态采用持久用户目录；不得继续依赖 /tmp。

## 原因与实际完成
- 实测 web-venv/bin/python 是指向 /tmp/insar-pilot-nextgen-venv/bin/python 的失效链接；pyvenv.cfg 同样指向临时环境。
- /tmp/insar-pilot-nextgen-venv 和 /tmp/insar-pilot-browser-state 均不存在。无法确认由哪个清理动作删除；不推断为用户操作。
- 原 launcher 固定 --state /tmp/insar-pilot-browser-state，属于此前本机安装配置缺陷。
- 先备份 launcher 和失效链接清单至 ~/.local/share/insar-pilot/repair-20260907/，仅移除该 venv/bin 下失效的 python/python3/python3.10 链接。
- 使用持久的 /home/griffin/miniconda3/envs/insar/bin/python -m venv --copies 重建 Web 解释器，保留现有 site-packages；当前 Python 是真实副本，base_prefix 为持久 insar 环境。仍需保留该基础 Python 的标准库，不宣称环境可任意搬迁。
- 新增 scripts/insar-pilot-web 并安装至 ~/.local/bin；检查解释器可执行后启动，使用应用默认 ~/.local/state/insar-pilot，不再硬编码临时状态。
- README 添加可复现的持久用户级安装与故障诊断。五份修改前指导已归档并保存 SHA256 清单。
- 工程目录、旧 Run/Artifact、科学输入未改动；临时状态中原有最近工程/下载记录/Library 无法从已不存在的原路径恢复。未做数据恢复或全盘数据盘点；仍存在的工程需按 .pilot 重新打开。

## 验证与证据
- 修复后导入 fastapi、uvicorn、insar_pilot.web.api 成功。
- Web Python 执行 pytest -q tests/test_web_launch.py tests/test_web_lifecycle.py：8 passed；已有 Starlette 弃用警告。
- /bin/sh -n scripts/insar-pilot-web 通过；无 Python 源码改动，无前端改动，无 SAR 计算。
- 从 /home/griffin 启动成功；最小 PATH（~/.local/bin:/usr/bin:/bin）下运行 insar-pilot-web --status 成功，证明无需激活 conda。
- 启动器调用 Windows 默认浏览器，未输出会话 token；未进行新的浏览器 UI 验收。
- MkDocs strict、git diff --check、5 份归档摘要与新增记录链接检查均通过。

## 服务与任务
- 修复前 8765 无监听；旧临时状态不存在，不能沿用上一轮任务统计。
- 新版真实服务已启动在 http://127.0.0.1:8765/，状态目录 ~/.local/state/insar-pilot。
- 最终 --status：RUNNING，0 download jobs、0 processing jobs、0 worker processes。
- 未启动独立测试服务或科学/下载 worker；保留用户已请求的 Web 服务运行。

## 下一步
- 当前任务已修复；用户直接运行 insar-pilot-web，存在的旧工程通过 .pilot 打开。
- 下一项开发仍从 handoff/index.md、current.md 和选定页卡进入；P02/D01 原边界保持。
- 临时环境/状态目录的历史路径仅作证据，不再作为安装或任务启动指令。
