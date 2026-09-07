# 公共外壳｜Conda/非 Conda 与双 ISCE 环境要求
日期：2026-09-07。阶段：要求澄清、代码核对与设计补充；没有实现新的通用运行时。
用户要求：兼顾使用/不使用 Conda 的用户，保证科学处理器 ISCE2/ISCE3 可用。
任务卡：[公共入口](../pages/shell-project-entry.md)。上一份：[启动修复](2026-09-07-web-launcher-repair.md)。

## 接受的决定与实际完成
- 明确 Web 与两种科学环境分别配置/检测，完整安装分别验收两种工作流；按所用 mission 阻断缺失能力，允许独立检索下载。
- 写入[运行环境支持合同](../../architecture/runtime-support.md)，列出 Conda/非 Conda/未安装路径、运行前门禁与真实代码缺口。
- 修正 README/安装文档中的范围表述；原 Qt 安装说明标为历史。修改前七份文档归档并保存摘要。
- 未将“无需 activate”夸大为“无 Conda 依赖”，也未将模块导入当作科学验收。

## 验证
- 本机 exact Python 子进程导入：insar 的 isce 2.6.5、insar-nisar 的 isce3 0.25.17 成功。
- 只读代码核对发现 runtime_environment/fingerprint 的 Conda 假设以及 profile 保存未执行完整 probe。
- 未重跑官方科学处理、CUDA、非 Conda 实机或新安装测试。未修改生产 Python/前端代码。
- MkDocs strict、git diff --check、新记录链接和 7 份归档 SHA256 核验通过。

## 服务与任务
- 未重启服务、未启动下载或科学 worker；本轮结束 --status 为 RUNNING，下载/处理/worker 均为 0。
- 本轮只读子进程已经退出，无自管后台测试服务。

## 下一步与索引
- 先按 runtime-support.md 的实施顺序完成通用环境解析/probe/门禁及安装入口，再声称两种安装生态完整支持；此为共享安装任务，不自动开展 NISAR 页面。
- 未决 D01 与 P02—P05 按页范围保持。handoff index/current/公共卡及 architecture overview/migration 已更新。
