# InSAR-PILOT

<p align="center"><img src="docs/assets/branding/logo.png" width="640" alt="InSAR-PILOT logo"></p>

**面向科研用户的本机 SAR/InSAR Web 工作台。**

[English](README_EN.md) · [当前架构](docs/architecture/overview.md) · [实施状态](docs/architecture/migration.md) · [Sentinel 页面划分](docs/architecture/sentinel-workbench.md)

## 当前开发方向

2026-09-05 起，Web 是唯一继续开发的产品端：先完善 Sentinel-1 / ISCE2 TOPS，再推进 NISAR / ISCE3。一个工程锁定一个传感器 Profile，两种传感器可使用不同处理页面。

近期目标是取得 phase stack；具体 SLC/缠绕干涉相位合同待确认。解缠排障和大范围相位数值评价暂缓，基础输入、执行和成果结构检查保留。五页职责已于 2026-09-06 确认，接下来按单页指令设计、实现和验收。

PySide6/Qt 界面停止继续开发。旧科学算法、下载核心、数据 reader、NISAR/openSEPPO 与验收证据继续复用和保留。

## 已有 Web 能力

- 工程创建/打开、数据绑定、配置修订、Library 引用。
- Sentinel ABCD/NISAR 分组检索、AOI 和纯影像底图、下载清单与暂停/继续/取消/重试。
- 支持 Linux 与 Windows 浏览器访问 WSL 的文件选择。
- 已准备输入的处理计划、运行历史、独立目录、日志、基础成果/QC 和地图。
- 中英文、明暗主题、可收起属性栏、明确的后台连接与退出提示。

当前是迁移预览版。专业参数表单、完整数据准备和成果交互仍需逐页完善。
已确认的五页方案尚未逐页实现；既有测试与科学执行边界见实施状态。

## 运行 Web 预览版

在仓库中建立独立应用环境，科学处理继续使用显式指定的原处理环境：

```bash
python -m venv .venv-web
.venv-web/bin/pip install -e '.[web]'
.venv-web/bin/insar-pilot-web
```

安装有可用启动命令时：

```bash
insar-pilot-web --no-browser
insar-pilot-web --status
insar-pilot-web --stop
```

Ubuntu 使用 Linux 浏览器；WSL 后台可由 Windows 浏览器连接 localhost。
关闭浏览器不停止后台任务；“退出应用”在没有活动任务时关闭服务。
发布资源包含编译后的前端；Node 用于前端开发。

当前安装元数据仍包含 Qt 依赖，`insar-pilot` 默认命令仍指向旧端。
这是待单独清理的安装/入口状态，不代表继续开发桌面端；当前请使用 `insar-pilot-web`。
本轮产品方向调整没有修改处理环境或安装入口。

## 开发与历史

阅读 [AGENTS.md](AGENTS.md)、[CONTRIBUTING](CONTRIBUTING.md) 和[工作交接索引](docs/handoff/index.md)。
[每页提示词](docs/handoff/prompts.md)用于启动设计、实现或接续任务。
当前规范只在 `docs/architecture/`；`docs/legacy/` 与 `archive/` 中的文件为历史证据。
旧指导按文件清单和 SHA-256 归档于 `archive/guidance/2026-09-05-before-web-sentinel/`。
该归档不是完整源码/数据备份；工作树现有修改和科学数据均保留。

[文档站点](https://wu-pengzhan.github.io/InSAR-PILOT/) 的线上内容可能早于当前本地工作树。
项目使用 [Apache-2.0](LICENSE) 许可证。
