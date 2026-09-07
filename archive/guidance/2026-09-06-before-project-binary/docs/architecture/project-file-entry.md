# 工程文件入口
日期：2026-09-06。用户已授权实施第一轮；**文件识别、新建、打开、最近工程及旧格式导入已实现并完成定向检查**。
范围为公共工程入口，不开展 P02 完整页面设计。
[任务卡](../handoff/pages/shell-project-entry.md) · [实施交接](../handoff/records/2026-09-06-project-file-implementation.md)。

## 工程文件与目录
Web 新建、从检索选择创建和旧工程导入使用“工程名.pilot”；已有 project.pilot 保持兼容。
一个工程根目录只允许一个 .pilot 主文件，多入口冲突明确拒绝。
显示名称与入口文件名解耦：修改名称产生修订，不自动重命名文件。
新建输入工程名和保存父目录，服务端预览最终目录/文件；旧 API 未指定 parent_directory 时仍按目标工程目录解释 path。
名称校验拒绝分隔符、跨平台保留名称及过长文件名，不静默修改用户输入。
EngineStore.create 保留 project.pilot 默认值供已有内部/CLI 调用兼容，Web 创建显式指定命名文件。

    YanAn/
      YanAn.pilot
      .insar_pilot/state.sqlite
      runs/
      workspaces/
      artifacts/
      cache/

.pilot 为可读 JSON，继续使用 schema_version=2，新建增加 format=insar-pilot-web。
旧无 format 的 Web 文件通过结构与数据库身份验证兼容，不批量改写；原 ID、修订、Profile 和科学语义保持。
SQLite 保存接受的修订与运行历史；实际入口路径贯穿修订、pending 恢复、手工修改导入。
恢复前核验身份/格式/Profile 锁定，只有已知 pending 能提交，无法识别的磁盘差异不自动覆盖。
凭据不进入工程描述；原始影像通过 Library/外部路径引用，大文件不嵌入 .pilot。

## 打开和最近工程
打开默认选择 *.pilot，服务端在分页前过滤文件扩展名，目录仍可导航。
选中后只读识别，展示名称、Profile、版本、入口路径和状态；旧响应不覆盖后来的选择。
/api/v1/projects/inspect 区分 ready、legacy、incomplete、invalid、unsupported、conflict、modified。
/api/v1/projects/creation-preview 只预览位置，不创建目录或数据库；实际提交重新校验。
/api/v1/projects/open 使用统一识别，兼容唯一入口的目录调用；有效 Web 工程才注册/恢复。
缺数据库、版本不支持、身份冲突或格式非法，不创建空历史。
外部修改提示需显式校验导入，保留 import-edits 后端能力；本轮未增加手工编辑导入 GUI。
最近工程显示文件位置、Profile、最近打开时间和可用性；读取列表不自动恢复工程事务，不可用项保留。
同 ID 同位置重复打开复用；同 ID 不同位置或同位置被其他 ID 占用明确拒绝，不静默重绑定。
本轮未提供工程搬迁/副本冲突消解向导。

## 旧 GUI 工程
根据内容识别并用原 ProjectStore 验证，不仅比较扩展名或 schema 数字。
旧工程显示“导入为新工程”，要求新名称和保存位置，复用导入服务生成新 ID/目录。
保留源配置、可核验输入和旧证据，缺失字段仍未知，旧 success 不变成新 SUCCESS。
敏感配置检查先于目标创建，导入完成后才登记最近工程。
无科学运行或隐式下载；失败的目标目录不会覆盖重用，重试需新位置。

## Linux 与 WSL
继续使用服务端文件选择器，浏览器不上传工程描述或 SAR 数据。
Linux 浏览本机路径；Windows 浏览器连接 WSL 时浏览服务可见路径及挂载盘，沿用 host_path 的发行版/盘符映射。
WSL 状态默认放 Linux 文件系统，保留 SQLite 锁语义要求。
系统双击关联未实现，需要后续启动器集成分发到正确发行版与服务。

## 后续范围
单独复制 .pilot 不是完整备份：历史依赖数据库、Run/Artifact 和外部数据。
工程搬迁/重命名管理、便携导出/另存副本、资源重新定位是后续独立任务。
工程内相对路径迁移尚未实施；已有绝对路径资产不能宣称复制目录后完全可复现。
移动需考虑活跃任务、数据库/WAL 一致性及数据依赖；当前只提供身份冲突保护。
本轮只交付公共入口，P01 原待验收与 P02—P05 分页状态保持。
