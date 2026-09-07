# P01｜检索与下载｜设计落盘与交接
日期：2026-09-06。
本次用户指令与范围：开始 P01 设计，核对现有功能，提出布局/交互/接口/验收方案，只设计这一页；随后要求 Implement the proposed plan，执行该方案的文档保存与交接步骤，不改产品代码。
阶段：设计。状态：设计待评审；文档交付完成不等于产品实现。
页面任务卡：[P01](../pages/p01-search-download.md)。
上一份记录：无 P01 专属记录；承接[指导与交接准备](2026-09-06-guidance-preparation.md)。

## 接受的决定与仍未知的事项

- 已接受（用户选择，2026-09-06）：首版聚焦 IW SLC；已选场景跨检索保留独立清单。
- 已接受基线：Web only、Sentinel first、五页职责、一个工程一个 Profile。
- 本次设计提案：筛选/地图/结果布局、查看与选择分离、三入口统一预览、保存选择与下载分开、结构化获取/资产合同和验收矩阵；按方案标设计待评审。
- 尚未确认：D01 phase stack 科学产品、looks/滤波；影响 P03—P05 和 P02 产品特有约束，不阻挡本页。
- 可独立继续：后续 P01 合同/GUI/定向验收；本次不自动执行产品实现或下一页。

## 实际完成

- 保存 [P01 设计](../../architecture/p01-search-download.md)：现状复用/缺口、桌面布局草图、响应式行为、ABCD/IW-SLC、AOI/纯影像、场景与清单、正常/空/失败/竞态状态、下载预览/控制/历史、接口与 16 组验收场景。
- 核对 DataExplorer、SearchMap、DownloadJobs、App、Web API、engine_data/download/control、ASF Sentinel adapter、ApplicationState/EngineStore 及相关测试代码；静态核对不是运行通过。
- 更新 P01 卡、总索引、current、migration、架构入口与 MkDocs 导航；P02 卡只增加依赖，P02—P05 仍待设计。
- 原 8 份指导/导航已先归档至 archive/guidance/2026-09-06-before-p01-design/，manifest.json 记录 SHA-256；原交接记录未覆盖。
- 未完成：产品 API/存储/前端开发、按设计的软件与浏览器验收、真实下载验证。
- 跨页合同提案：P02 接收 provider+remote ID、查询/AOI 来源、获取计划、文件角色、Library asset/version 和状态/校验依据；不改写处理 AOI，partial 不作可处理数据。
- 兼容：保留旧 product_ids 唯一解析、现有控制端点和终态历史；未知字段不补造。上述为待实现合同，本轮没有迁移数据库。

## 验证与证据

- 工作位置为 WSL /home/griffin/projects/insar-pilot；Windows C:/home/griffin/projects/insar-pilot 仅有少量文件，不是完整工作树。
- HEAD 为 31ccf3afd23c2ea118dfe8bc99c0697bd5f505ec；大量原有修改/未跟踪文件保留，不执行 reset/clean。
- Web Python 执行 python -m mkdocs build --strict --site-dir /tmp/insar-pilot-p01-design-docs：通过（退出码 0），日志 artifacts/p01-design-2026-09-06/mkdocs-build.log。构建输出包含现有未入导航页面 INFO 和 Material 版本公告，不是新增文档错误。
- git diff --check：通过，日志 git-diff-check.log；新增 Markdown 另做行尾空白检查。
- python3 artifacts/p01-design-2026-09-06/verify_docs.py：通过；9 份文档的 86 条本地链接、8 份归档 SHA-256、365 份产品/测试/脚本/配置文件内容及文件集合保持一致、16 组验收条目和构建 HTML 存在检查通过。机器可读结果为 validation.json。
- verify_docs.py 与上述日志均在证据目录；本次只验证文档及未改产品的边界，不做页面视觉验收。
- 证据目录：artifacts/p01-design-2026-09-06/；产品文件修改前 SHA-256 清单为 product-baseline.json。
- 未运行 Python 软件测试、npm test/build、浏览器 E2E、真实 ASF 检索/下载或科学计算；本次仅文档变更，16 组验收矩阵为未来要求，不是通过证据。
- 科学参数、历史数据和已发布成果未修改；fixture 和真实数据均未启动验证，旧测试数不作为新结果。

## 服务与任务

- 本次未启动/停止服务、worker、下载或浏览器测试进程；不占用新端口。
- 2026-09-06 设计保存前 launcher --status：RUNNING，0 download jobs、0 processing jobs、0 worker processes；为瞬时只读观察。
- 最终只读检查时间：2026-09-06T09:03:11+08:00；launcher --status 输出为：RUNNING — 0 download jobs, 0 processing jobs, 0 worker processes. 用户服务继续运行。
- 用户服务只做状态查询，无重启/退出操作。不读取或记录 token、凭据或秘密环境变量。
- 文档构建写入独立 /tmp/insar-pilot-p01-design-docs/；无需要终止的测试进程。

## 下一步

- 下一位先读 AGENTS、总索引/current、P01 卡、本记录及 P01 详细设计。
- 精确下一动作：在后续 P01 产品实现任务中，先落实 typed 获取预览/selection/Library 合同、revision/幂等及旧记录兼容测试，再实现筛选/选择/地图、统一清单与下载管理，最后完成定向验收。
- 待用户决定：设计评审修改意见（如有）；D01 在相关下游任务前集中明确，本页不重复询问。
- 索引、任务卡、current、migration 与导航已同步为设计待评审；P02 仅登记上游依赖，不自动开展 P02。
