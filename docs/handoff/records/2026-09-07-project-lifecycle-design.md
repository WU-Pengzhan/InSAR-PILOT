# 公共外壳｜工程选择与目录统筹设计
日期：2026-09-07。
本次用户指令与范围：规划启动先选工程、未打开仅下载、.pilot 打开及工程 data/processing 分区。
阶段：设计；未修改产品代码。
页面任务卡：[公共入口](../pages/shell-project-entry.md)。
上一份公共记录：[二进制封装](2026-09-06-project-binary.md)，保持原样。

## 接受的决定与仍未知的事项
- 启动先选择、未打开只允许检索下载、.pilot 打开及目录+名称新建为用户要求。
- [设计](../../architecture/project-lifecycle-layout.md)提出具体子目录、products 独立、项目新下载入 data/既有数据引用、版本化兼容。这些细节是本轮建议，不标作用户已验收。
- 新页面加载/刷新回首页、仅事件重连不清除已打开工程；建议先实施入口再实施目录。
- phase stack D01 不在本轮决定，P02—P05 仍待逐页设计。

## 实际完成
- 核实 App.vue initialize 通过 pilot-project 自动选择；selectProject 打开 data 页。
- 核实 ProjectEntry 父目录+名称预览与 .pilot 打开已实现。
- 核实 EngineStore 多处直接拼接根目录 runs/workspaces/artifacts；下载固定到应用 Library。
- 保存状态矩阵、目录建议、数据所有权/冻结下载目标、布局版本/旧工程不搬迁、API 影响与 A/B 分步验收。
- 没有执行启动修复、目录改造、用户工程移动、下载或科学处理。
- 10 份受影响指导原文件及 SHA-256 清单已归档至 archive/guidance/2026-09-07-before-project-lifecycle-design/。

## 验证与证据
- 只读核对代码与旧交接，工作树大量原有修改保留。
- 106 个相对文档链接、10 份归档 SHA-256 校验通过；MkDocs strict 构建通过（输出 /tmp/insar-pilot-project-lifecycle-docs-20260907）。
- 未运行软件/浏览器/科学测试，本轮无产品实现；新交互不能宣称已通过。
- 原始输入、黄金数据、.pilot、数据库及历史成果没有修改。

## 服务与任务
- 启动核对用户服务 RUNNING：0 下载任务、0 处理任务、0 worker。
- 未启动自管服务或测试 worker，不重启/停止用户服务，无测试进程需清理。
- 最终重新核对仍为 RUNNING，0 下载/处理任务、0 worker；用户服务保持原状。

## 下一步
- 从本记录、公共任务卡和新设计接续；先实施 A 启动/无工程守卫/打开关闭，再独立实施 B 目录解析/下载归属。
- 代码入口 App.vue、ProjectEntry.vue、engine_store.py、engine_download.py、acquisition.py 和 web/api.py。
- 首页状态/数据引用语义应由后端事实驱动，不把新文件夹当处理就绪。
- index/current/公共卡/P01/P02/migration 与相应架构入口已更新；旧记录未覆盖。
