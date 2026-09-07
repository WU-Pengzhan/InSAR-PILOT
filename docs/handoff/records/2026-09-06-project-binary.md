# 公共外壳｜.pilot 二进制封装
日期：2026-09-06。用户要求“不希望能够直接被打开编辑”，不要求密码。
阶段：实现与定向验收。
[任务卡](../pages/shell-project-entry.md) · [当前合同](../../architecture/project-file-entry.md)。
上一份：[工程入口实现](2026-09-06-project-file-implementation.md)，原样保留。

## 接受的决定与仍未知的事项
- .pilot 默认采用专用二进制容器，减少普通文本编辑器误编辑。
- 不做密码加密、数字签名或大型成果单文件打包。
- 旧 Web JSON 只读打开不改写，下次通过软件保存配置时封装；旧 GUI 源工程不变。
- 文件关联、备份/搬迁与 P02 科学未决项不变。

## 实际完成
- infrastructure/project_codec.py：版本化魔数/长度/摘要/zlib 容器；JSON 兼容读取；有界解压、截断/尾随/损坏检查，不使用可执行反序列化。
- engine_store.py：工程创建、修订、配置导入及恢复使用统一编解码；编码大小检查先于 pending 插入。
- 抽出 atomic_bytes 复用既有 fsync/replace 写入协议；atomic_json 为其他快照/manifest 保持相同 UTF-8 内容与换行。
- project_file.py：统一识别容器或旧 JSON；未知容器版本为 unsupported，损坏为 invalid。
- 保持内部 schema、Project ID、名称/Profile/科学配置及历史记录；SQLite、日志和科学成果格式不变。
- 无前端或 OpenAPI 合同修改，无用户工程批量转换；无科学执行。
- 七份原指导文档与摘要归档在 archive/guidance/2026-09-06-before-project-binary/。

## 验证与证据
- Web Python：project_codec、project_file_entry、engine_store、engine_recovery、engine_asset_closure、engine_api、engine_jobs、p01_acquisition 共 84 passed。
- 覆盖新文件非 JSON 文本、Unicode 往返、旧 JSON 打开不变/保存转换、损坏头/载荷/摘要/长度/尾随、未知版本、解压上限、替换失败保持原文件、文件已发布但数据库未提交的恢复。
- Ruff 修改的三份源文件及两份测试通过；Mypy 三份源文件通过（沿用 Web 依赖路径及第三方 import-untyped 限制）。
- Linux Firefox/Chromium：工程打开/新建/旧格式导入共 6 passed；Windows Edge→WSL 同流程 3 passed。
- 浏览器证据 artifacts/project-binary-2026-09-06/；新工程由真实后端创建为二进制，源 legacy 为隔离 fixture。
- 无前端源码变化，未重复前端构建/单元测试；复用上一轮构建的静态界面。
- 未执行真实用户项目迁移、科学计算、原生缩放矩阵、密码加密或系统双击关联验收。
- 摘要用于完整性检测，不宣称有意修改不可行或内容保密。

- MkDocs strict、git diff --check、受影响文档链接及七份归档摘要检查通过；fixture 进程已确认不存在。

## 服务与任务
- 用户服务本轮核对为 STOPPED，无活跃 worker/任务；没有重启用户服务。
- 独立 fixture PID 212154、端口 8767；身份核实后 SIGTERM 清理。
- 未创建用户科学/下载任务，未保存凭据；旧工程/黄金数据保持原样。

## 下一步
- 从本记录、任务卡和工程文件合同接续。
- 下次启动软件后，新建或保存工程即使用二进制封装；已有 JSON 工程仍能打开。
- 不自动推进 P02、搬迁/备份或系统关联。
- index/current/任务卡/project-file-entry/project-model/storage/migration 已同步，旧记录未改写。
