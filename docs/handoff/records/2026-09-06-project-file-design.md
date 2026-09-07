# 公共外壳｜工程文件入口设计
日期：2026-09-06。用户要求规划 .pilot 工程入口并询问设计意见。
阶段：设计，未修改产品代码。
[任务卡](../pages/shell-project-entry.md) · [设计提案](../../architecture/project-file-entry.md)。
上一份共享外壳记录：[地图与面板](2026-09-06-p01-map-panel.md)。

## 接受的决定与仍未知的事项
- 用户希望以独特工程文件打开工程，当前目录入口不符合期望。
- 本轮建议工程名.pilot 加配套目录，明确内容识别、既有 project.pilot 兼容及旧 GUI 导入。
- 任意命名、完整第一轮交付范围仍是建议，未宣称用户已接受；P02 完整布局尚未开展。
- phase stack 科学选择无新增决定。

## 实际完成
核对 EngineStore、Web open API、App.vue、FilePathField、legacy ProjectStore 和现有 project/storage 规范。
现有 JSON 文件已存在，界面目录模式是直接缺口；任意命名还涉及存储修订/恢复硬编码。
设计覆盖新建/打开/最近工程、格式识别、文件/数据库一致性、丢失状态、legacy 导入、路径与搬迁边界。
跨页仅提出公共打开入口和状态解析合同，没有实施 API 或改动历史资产。

## 验证与证据
只读源码核对；MkDocs strict、受影响文档相对链接与四份归档摘要检查通过。无软件/科学测试；本次不把过去测试当新结果。
未运行 SAR、下载或修改工程数据；操作系统文件关联与新入口均未测试，因为未实现。
修改前四份指导索引保存在 archive/guidance/2026-09-06-before-project-file-design/，附摘要清单。

## 服务与任务
本轮 launcher --status 为 STOPPED，无活跃应用 worker/任务；未启动测试服务器、下载或科学任务。
没有需要清理的本轮进程，没有保存凭据。

## 下一步
先读任务卡及设计提案。用户讨论后按明确实施范围接入文件识别、存储/API 和外壳界面；不自动开展 P02 全页。
已更新 index/current/P02 依赖/migration。该提案未替代现行 project-model/storage 合同。
