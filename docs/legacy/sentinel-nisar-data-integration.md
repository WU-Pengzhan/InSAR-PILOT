> LEGACY / HISTORICAL EVIDENCE. Not an active architecture specification.

# Sentinel-1 / NISAR 数据整合里程碑与 Codex Prompt 流程

本文定义“Sentinel-1 / NISAR 数据整合完成”的准确边界、目标架构、验收数据和可顺序交给 VSCode Codex 执行的开发 prompts。P1–P4 后端合同已于 2026-09-04 落地；同日已新增生产 NISAR ASF RSLC Provider、KML/SHP AOI、RSLC 下载、openSEPPO 子集，以及 ISCE3 RIFG/RUNW/GUNW CLI、Runner 和 Validator。Web UI 仍按本文后续顺序开发。

## 1. 当前基线

当前产品状态必须按三层区分：

| 层级 | Sentinel-1 | NISAR |
|---|---|---|
| 远程检索 | 生产 ASF Provider 已接入 | 生产 ASF RSLC Provider 已接入，支持 AOI/path/frame/PR-UR 等约束 |
| 本地数据 | 新 Reader/Import/Catalog 可只读登记 ZIP/SAFE；旧 GUI 仍走原入口 | 新 Reader/Import/Catalog 可只读登记 RSLC HDF5；尚未接 UI |
| InSAR 处理 | ISCE2 `topsStack` 可用且必须保持回归兼容 | Qt-free CLI 已实际完成 AOI subset → ISCE3 RIFG/RUNW/GUNW 并验证输出；尚未接 Workbench Task UI |

因此，“数据整合完成”不是“已经完成 NISAR InSAR 处理”，而是建立一条稳定、可检查、可扩展到 ISCE3 的统一数据入口。

## 2. 里程碑定义

本里程碑完成后，Workbench 必须能够：

1. 只读导入 Sentinel-1A/B/C/D SLC ZIP/SAFE 和 NISAR RSLC HDF5。
2. 将两类原始产品投影为统一的逻辑产品、资产引用和可检查元数据，不转换或复制大文件。
3. 在同一个 Data Catalog 中显示、筛选、选择和检查两类产品。
4. 对同 mission 产品执行 pair/stack 兼容性检查，并明确拒绝 Sentinel-1 与 NISAR 组成干涉对。
5. 根据产品 capability 投影可用 Workflow Recipe 和 Task；不把 Sentinel TOPS 专用步骤暴露给 NISAR，也不把 NISAR 专用参数暴露给 Sentinel。
6. 保持现有 Sentinel-1 + ISCE2 工作流可用，并为下一里程碑的 NISAR ISCE3 RIFG Backend 提供稳定输入契约。

“完成”不包括：

- NISAR GSLC 输入支持；
- Sentinel-1/NISAR 跨 mission 干涉处理；
- ALOS 本地导入或处理；
- 在本里程碑内实现完整 RIFG/RUNW/GUNW 执行；
- 将 SAFE 与 HDF5 转换成统一物理格式；
- 导入、选择、下载或任务完成后自动可视化；
- 为尚未验证的 workflow 添加可点击但不可运行的占位入口。

## 3. 统一边界

统一发生在数据语义、Catalog、任务协议和 GUI 外壳；mission 差异保留在 Reader、兼容性规则和 Workflow Recipe 中。

```text
Workbench Data Workspace
        ↓
Local Import Application Service
        ↓
Local Product Reader Registry
        ├── Sentinel1SafeReader  → ZIP / SAFE / manifest.safe
        └── NisarRslcReader      → HDF5 /science/LSAR/RSLC
        ↓
Canonical LocalSARProduct + AssetRef
        ↓
Project Data Catalog
        ↓
Compatibility / Eligibility Services
        ↓
Workflow Recipe Registry
        ├── sentinel1.tops.isce2
        └── nisar.rslc_pair.isce3（本里程碑只声明稳定输入契约）
```

### 3.1 Canonical 产品不是统一文件

建议的逻辑模型至少能够表达：

```text
product_id
mission / platform
product_type
acquisition_mode / acquisition_layout
start_time / end_time
orbit_direction / orbit identity
track / frame / relative orbit
frequency_bands / polarizations
footprint
assets
native_metadata
reader_id / reader_schema_version
```

资产引用必须同时支持普通文件和 HDF5 内部 dataset：

```text
AssetRef
├── uri: /path/to/S1...zip
├── subdataset: null
└── role: source_product

AssetRef
├── uri: /path/to/NISAR...h5
├── subdataset: /science/LSAR/RSLC/swaths/frequencyA/HH
└── role: complex_radar_image
```

不得假设“一个逻辑产品等于一个平面文件”。NISAR 的一个 HDF5 文件包含多个频段、极化、坐标和元数据 dataset；Catalog 必须保留这些引用关系。

### 3.2 Sidecar 策略

原始数据保持只读。Catalog 可以在项目元数据目录生成机器可校验的 JSON sidecar，例如：

```text
.insar_pilot/catalog/products/<product_id>.sar.json
```

sidecar 是派生索引，不是原始数据的替代品。若以后需要 GAMMA 风格 `.par`，它应由同一 canonical metadata 显式导出，不能成为第二个权威状态源。

## 4. Task 适用性规则

Task 是否共用，按输入输出语义、参数语义、执行机制和验收规则判断。

| 类型 | 共同或专用 Task | 规则 |
|---|---|---|
| 完全共用 | Import、Inspect Metadata、Catalog、Select Products | 使用同一 Application Service，Reader 负责格式差异 |
| 语义共用、实现不同 | Validate Pair、Prepare DEM、Build Interferogram、Catalog Results | 暴露同一用户目标，由不同 Recipe/Backend 展开 |
| Sentinel 专用 | SAFE/IPF/AUX、EOF、IW/burst、ESD/NESD、burst merge、topsStack run files | 只对 Sentinel TOPS + ISCE2 capability 可见 |
| NISAR 专用 | HDF5 RSLC schema、frequency A/B、frame/track、runconfig、dense offsets、rubbersheet、RIFG/RUNW/GUNW | 只对 NISAR RSLC + ISCE3 capability 可见 |

本里程碑应定义 Qt-free 的 `TaskDescriptor` 或等价契约，至少包含：

```text
task_id
applicable_missions
required_product_types
input_roles / output_roles
parameter_schema
workflow_recipe_id
backend_id
overwrite_policy
```

但不得在数据整合阶段实现自由 DAG 编辑器或伪造 NISAR 可执行状态。

## 5. GUI 目标

Data Workspace 复用 Workbench shell 和统一布局策略：

```text
┌ InSAR-PILOT Workbench ───────────────────────────────────────────────┐
│ Data                                                               │
├──────────────────────┬───────────────────────────────────────────────┤
│ Sources              │ Data Catalog                                  │
│ [Add files/folder]   │ Mission · Type · Time · Mode · Status         │
│                      │ QTableView / QAbstractTableModel               │
│ Import summary       ├───────────────────────────────────────────────┤
│ [Advanced ▸]         │ Inspector / Pair compatibility（按需显示）    │
├──────────────────────┴───────────────────────────────────────────────┤
│ Tasks / Errors / Logs（默认收起）                                   │
└──────────────────────────────────────────────────────────────────────┘
```

约束：

- 默认只显示数据源、Catalog 和一个主要导入动作；
- Inspector、native metadata、HDF5 dataset 列表和完整路径默认折叠；
- 文件夹扫描、ZIP manifest 解析和 HDF5 元数据读取不得在 GUI 主线程执行；
- NISAR 大文件只能按需读取小型 dataset/attribute，不得加载完整影像数组；
- 选择产品不会自动可视化；
- mission-specific Processing 参数不进入 Data Workspace；
- 不使用一组巨大控件通过 show/hide 同时模拟 Sentinel 和 NISAR 页面。

## 6. 真实数据与验收方式

只读 characterization 数据：

| 用途 | 路径 |
|---|---|
| Sentinel 最小端到端样本 | `/home/griffin/insar_projects/YanAnHighway/data/SLC` |
| Sentinel 批量/性能样本 | `/home/griffin/insar_projects/HKIA_S1/SLC` |
| NISAR RSLC 黄金样本 | `/home/griffin/insar_projects/golden/nisar` |
| NISAR 成功 RIFG 原型证据 | `/home/griffin/insar_projects/golden/nisar/phase2` |

开发和测试不得移动、重命名、解压、覆盖或在上述目录生成 sidecar。需要写入时使用 `tmp_path`、`mktemp -d` 或项目内明确的临时测试目录，并在测试结束后只清理自己创建的目标。

CI 不复制 29 GB RSLC。单元测试使用最小合成 HDF5 fixture；真实数据只用于本机 opt-in characterization test。真实测试必须记录耗时、峰值内存、读取的 dataset/attribute 和零写入证明。

## 7. 顺序化 Codex Prompt 流程

建议一个 prompt 对应一个独立 Codex 任务，按 P0 → P6 顺序执行。每个任务开始前检查上一阶段的差异和测试报告，不并行修改共享 domain 模型。

所有 prompts 都继承以下固定约束：

```text
工作目录：/home/griffin/projects/insar-pilot
保留脏工作树中的既有修改；不得 reset、checkout、clean 或提交。
先读取 docs/refactoring-roadmap.md、docs/architecture.md 和
docs/sentinel-nisar-data-integration.md。
保持旧 MainWindow、Sentinel-1 + ISCE2 流程和 Workbench 搜索行为可用。
NISAR 只支持 RSLC，拒绝 GSLC；ALOS 仍为 search-only。
真实数据目录只读；所有写测试使用临时目录。
可视化只能由用户显式调用。
Qt-free 逻辑进入 domain/application/services/providers；GUI 保持薄。
完成后报告：修改文件、关键设计、测试命令和结果、未完成风险。
```

### P0：现状审计和契约冻结

```text
目标：为 Sentinel-1/NISAR 数据整合建立可执行基线，本任务只读分析和补充文档/测试计划，不实现新功能。

请完成：
1. 盘点当前 Search、ProjectDocument、InputCatalogService、ResultCatalogService、Workbench 和旧 ISCE2 入口。
2. 明确哪些当前模型是 Sentinel 专用，不能直接扩展成统一模型。
3. 对 YanAnHighway、HKIA_S1 和 golden/nisar 做只读格式统计与轻量元数据检查。
4. 建立测试矩阵：Sentinel ZIP/SAFE、NISAR RSLC、损坏文件、错误产品类型、空目录、重复导入、长路径、大批量和取消。
5. 给出拟新增模块和迁移顺序；不得移动现有 Sentinel 服务。

验收：报告包含代码证据、真实数据证据、风险清单和下一阶段精确接口建议；工作树除明确文档外无数据或运行产物变化。
```

### P1：Canonical 本地产品与 Reader 契约

```text
目标：实现 Qt-free、不可变、mission-neutral 的本地 SAR 产品和资产引用模型，以及 Reader Protocol/Registry；暂不接 GUI。

请完成：
1. 定义 LocalSARProduct、AssetRef、acquisition layout/native metadata 引用及稳定 product_id 规则。
2. AssetRef 必须支持普通文件和 HDF5 subdataset，不把 provider SDK/h5py 对象带出 Reader。
3. 定义 LocalSARProductReader 的 probe/read 接口、SupportReport、统一错误类型和 Reader Registry。
4. Registry 校验 reader_id、schema version、重复范围和产品能力冲突。
5. 添加纯单元测试，并验证 dataclass/serialization 的确定性。

禁止：修改旧 WorkflowConfig 来堆入 NISAR 字段；实现 HDF5 Reader；接入 QWidget；复制真实数据。

验收：domain/application 层无 Qt、h5py、ASF SDK 依赖；模型能够表达 Sentinel ZIP/SAFE 和 NISAR HDF5 dataset 引用。
```

### P2：Sentinel-1 与 NISAR Readers

```text
目标：在 P1 契约上实现两个生产级只读 Reader，不进行数据转换。

请完成：
1. Sentinel1SafeReader 支持 ZIP 和 .SAFE，读取 manifest.safe，解析 platform、mode、时间、轨道、极化、footprint 和 IPF；显式支持 A/B/C/D，无法识别时明确失败。
2. NisarRslcReader 使用可选 h5py 依赖，验证 HDF5 signature、/science/LSAR/identification 和 /science/LSAR/RSLC；只接受 productType=RSLC，拒绝 GSLC/GUNW/RIFG 作为输入 RSLC。
3. NISAR Reader 解析 mission、product level、track、frame、look direction、时间、frequency/polarization 和 footprint，并生成 HDF5 subdataset AssetRef。
4. probe 必须轻量、可取消，不读取完整复数数组。
5. 用最小合成 ZIP/SAFE/HDF5 fixture 覆盖成功、缺字段、损坏、错误类型和多频段。
6. 添加 opt-in 真实数据 characterization 命令，但默认 pytest 不依赖真实数据。

验收：真实 YanAn/HKIA Sentinel 和两景 NISAR RSLC 可只读投影为统一产品；真实目录零写入；NISAR 大文件读取不随影像大小线性增长。
```

### P3：Local Import Service、Catalog 与 sidecar

```text
目标：把 Readers 接入统一导入服务和项目 Data Catalog，支持 dry-run、重复导入和持久化恢复；暂不接 GUI。

请完成：
1. 实现 LocalImportApplicationService：文件/文件夹输入、Reader 选择、后台可取消扫描所需的 Qt-free API、逐项错误和汇总结果。
2. 实现 ProjectDataCatalog，保存逻辑产品、AssetRef、reader/schema version、来源快照和导入时间。
3. sidecar 只写入项目 .insar_pilot/catalog，不写原始数据旁边；采用原子写入和 schema_version。
4. 重复导入按稳定 product_id 合并；文件发生变化时给出 stale/changed 状态，不静默覆盖元数据。
5. 保持旧 project.pilot 可读；新字段必须有防御性 from_dict 和类型转换。
6. 测试 dry-run 零写入、取消、部分失败、重复导入、旧项目兼容和原子写失败。

验收：同一 Catalog 可同时持有 Sentinel 与 NISAR 产品；关闭并重新打开项目后结果一致；原始数据保持只读。
```

### P4：兼容性、Pair/Stack 与 Workflow Eligibility

```text
目标：明确哪些产品可组成 Sentinel stack、NISAR pair，哪些 Task/Recipe 可用；不执行 ISCE2/ISCE3。

请完成：
1. 定义 PairCompatibilityReport、WorkflowRecipeDescriptor 和 TaskDescriptor（或等价不可变模型）。
2. Sentinel 规则覆盖 mission/platform、TOPS mode、轨道方向、relative orbit、swath/burst/极化和时间；保留现有 ISCE2 能力映射。
3. NISAR 规则覆盖 RSLC、track/frame、look direction、frequency/polarization、空间/时间覆盖；GSLC 明确拒绝。
4. Sentinel-NISAR 跨 mission pair 必须返回明确 incompatible reason，不能尝试降级。
5. Recipe Registry 只投影实际支持项：Sentinel 指向现有 ISCE2；NISAR 只声明未来 ISCE3 RIFG 的输入契约并标记 backend unavailable，不能提供可点击 Run。
6. 测试 applicability 不泄漏：TOPS ESD 不适用于 NISAR，NISAR rubbersheet/runconfig 不适用于 Sentinel。

验收：给定任意 Catalog selection，Application Service 能稳定返回 compatible/incompatible 和可用 Recipe/Task，不依赖 GUI 字符串判断。
```

### P5：Workbench Data Workspace

```text
目标：将统一导入和 Catalog 接入新 Workbench，遵守既有 GUI 性能和视觉约束；不接处理执行和默认可视化。

请先更新低保真 wireframe，再实现：
1. Data Workspace 的 Add files/Add folder、Import summary、QAbstractTableModel Catalog、临时 Inspector 和 Pair compatibility。
2. 文件扫描和 Reader 调用在后台执行，支持取消、latest-wins 和逐项错误；GUI 不接收 h5py/zipfile 原生对象。
3. Mission、product type、mode、frequency/polarization 列由 canonical model 投影。
4. 选择 Sentinel/NISAR 时只显示 capability 允许的检查和后续动作；backend unavailable 时显示简短状态，不显示 Run。
5. Advanced metadata、完整路径、HDF5 dataset、Tasks/Logs 默认折叠。
6. 搜索结果选择与本地 Catalog 选择仍是不同 ID 空间，不得混用 remote_product_id 和 local product_id。

验收：Normal/Maximized × 中英文 × 100/125/150% DPI；空、扫描、结果、部分失败、取消、错误、长路径、大批量状态全部检查；滚动、splitter、窗口恢复无明显卡顿；无自动可视化。
```

### P6：整合验收与下一里程碑交接

```text
目标：以真实 Sentinel/NISAR 数据完成只读整合验收，并形成 ISCE3 RIFG Backend 的稳定输入合同；原则上只修复验收发现的问题。

请完成：
1. 在临时项目中导入 YanAnHighway 的 2 景 Sentinel、HKIA_S1 的 51 景 Sentinel 和 golden/nisar 的 2 景 RSLC；禁止修改源目录。
2. 验证 Catalog 重开一致性、重复导入、批量性能、取消、pair compatibility 和 Task applicability。
3. 验证旧 MainWindow、旧 project.pilot、Sentinel ISCE2 输入扫描和结果 Catalog 回归。
4. 运行 pytest、ruff、mypy、git diff --check 和 GUI 截图矩阵；记录真实数据测试耗时与内存。
5. 更新 architecture/refactoring-roadmap/user-facing docs，区分已实现和下一阶段能力。
6. 生成下一里程碑“ISCE3 NISAR RIFG Backend”的输入/输出合同：两景 RSLC、DEM、frequency/polarization、runconfig、scratch、RIFG product、日志和验收 manifest。

验收：“数据整合完成”清单逐项有证据；没有宣称 RUNW/GUNW 已完成；工作树既有修改和真实数据均被保留。
```

## 8. 里程碑完成判定

只有同时满足以下条件，才能将状态标记为完成：

1. Sentinel ZIP/SAFE 与 NISAR RSLC 使用不同 Reader、同一 canonical product contract。
2. 同一 Catalog 能持久化并恢复两类产品及其文件/HDF5 dataset 资产引用。
3. Reader/Import/Catalog/Compatibility/Eligibility 均为 Qt-free 且有单测。
4. 跨 mission pair 被明确拒绝；同 mission 兼容性给出结构化 reason。
5. Sentinel TOPS 与 NISAR 专用 Task 不互相泄漏。
6. 新 Workbench 可后台导入、取消和检查数据，且不自动可视化。
7. 旧 Sentinel-1 + ISCE2 流程和现有搜索 Workbench 无回归。
8. 真实数据只读验收通过；大型 NISAR 文件没有整幅加载或复制。
9. 当前产品不显示虚假的 NISAR Run 入口。
10. 下一里程碑 ISCE3 RIFG Backend 已获得稳定、版本化的输入输出合同。

## 9. P0 现状审计与接口冻结（2026-08-31）

本节是对当前工作树和指定真实数据执行的只读审计。它冻结 P1 的输入合同，不表示 P1
Reader、Project Data Catalog 或 Data Workspace 已经实现。代码行号以本次审计工作树为准；
后续重构时应优先依赖符号名和测试，而不是依赖行号。

### 9.1 证据范围和状态口径

| 状态 | 含义 | 本次结论 |
|---|---|---|
| 当前已实现 | 产品代码中有生产入口，并由当前测试约束 | ASF Sentinel-1 远程检索；旧 Sentinel ZIP/SAFE 扫描、ISCE2 `topsStack` 生成与运行；ISCE2 merged 输出发现；显式结果预览 |
| 原型证据 | 真实目录中存在外部工具生成的配置、日志和验收产物，但产品代码没有对应入口 | `golden/nisar/phase2` 中一次 NISAR A/HH RIFG 成功结果 |
| 目标能力 | 只有本文合同和测试计划，当前产品不可调用 | NISAR RSLC Reader、统一 `LocalSARProduct` / `AssetRef`、Project Data Catalog、兼容性与 Workflow Eligibility、Workbench Data Workspace |

NISAR RSLC 和 ALOS 的 fake-provider 测试属于“领域契约证据”，不是生产 provider。NISAR
GSLC 目前在远程 Search Application Service 中被提前拒绝，但尚无本地 Reader，因此这不能
替代本地产品类型校验。ALOS 继续保持 search-only，不进入下面的本地 Reader、Catalog 或
processing 范围。

### 9.2 当前代码盘点

#### Search

- `domain/search/models.py` 定义不可变的 `SearchRequest`、`RemoteSARProduct`、
  `SearchPage`、`ProviderDescriptor`、`SearchCapability` 和 `SupportReport`。这里的模型描述
  远程查询及结果，`remote_product_id` 明确不是本地 Catalog ID。
- `application/search/service.py` 负责跨 mission 请求校验、provider 选择和返回值边界校验；
  第 34–36 行只接受 NISAR RSLC，并明确拒绝 GSLC。它也阻止 provider SDK 对象通过
  `footprint` 或 `provider_metadata` 泄漏到 GUI。
- `providers/sar/base.py` 的生产 Protocol 当前是 `supports(request)` / `search(request)`；
  `providers/sar/registry.py` 禁止把 processing capability 注册进 Search Registry。
- `providers/sar/__init__.py` 的默认生产 Registry 只注册
  `ASFSentinel1SearchProvider`。该 adapter 复用旧 `download/providers/asf_provider.py`，
  并把 `SceneRecord` 转为 `RemoteSARProduct`，没有复制 ASF 查询实现。
- `SearchTaskRunner` 和 `BackgroundTaskPool` 提供后台执行、latest-wins 和结果抑制。当前
  cancel 不会中断已经进入 provider 的网络调用；`TaskHandle.cancel()` 的合同只是抑制返回，
  实际硬边界仍是网络 timeout。这一点不能照搬为大目录/大 HDF5 的 Reader 取消合同。

结论：Search 的 domain/application/provider 分层可以作为新本地数据边界的结构参考，
但 `RemoteSARProduct` 不能改名或加字段后充当 `LocalSARProduct`，Search Registry 也不能
注册本地 Reader 或 processing backend。

#### ProjectDocument 和持久化

- `domain/project.py` 的 `ProjectDocument` 当前 `schema_version=1`，只包含 `workspace`、
  `environment`、`workflow`、`download`、`visualization` 和 `state`。
- `WorkflowConfig` 直接表达 `stackSentinel.py` 参数：orbit/AUX、IW swath、NESD/ESD、
  reference date、looks、connections 和 run-file work directory。
- `InputEntry` / `PreparedInputs` 表达 SAFE/ZIP 路径、IPF、AUX_CAL 和
  `safe_inputs.txt`，随后直接进入 `stackSentinel.py -s`。
- `DataDownloadConfig` 和 `download/models.py` 的 `SearchCriteria`、`SceneRecord`、
  `DownloadTask` 均以 Sentinel-1 ASF、SLC/EOF/DEM 和 scene 为语义中心。
- `ProjectWorkspace.slc_dir()` 固定映射到 `data/SLC`；`ProjectStore.create_workspace()`
  同时把该路径写入旧 `WorkflowConfig`，并写出 Sentinel-1 acquisition 提示。
- `ProjectStore` 只接受 schema 1、限制 `project.pilot` 为 8 MiB，当前 `save()` 使用直接
  `write_text`。大批量产品和 native metadata 不应直接塞进 `ProjectDocument`。

结论：`ProjectDocument` 继续作为旧流程状态源；P3 只在其中增加一个小型、可向后读取的
Catalog 引用配置，产品实体写入 `.insar_pilot/catalog` 的版本化 index/sidecar。不得把
NISAR runconfig、frequency、dense offsets、rubbersheet 或 ISCE3 输出路径加到
`WorkflowConfig`。

#### InputCatalogService

- `services/input_catalog.py` 明确声明为 `stackSentinel.py` 准备 SAFE/ZIP manifest。
  `scan()` 只识别 `.SAFE` 目录和 `.zip` 文件并读取 `manifest.safe` 的 IPF version。
- 任一损坏 ZIP、缺失 manifest 或 XML 错误会中止整个 scan，没有逐项错误、Reader probe、
  稳定 product ID、重复合并、dry-run 或取消检查。
- `prepare_inputs()` 会在 work directory 写 `safe_inputs.txt`，并可调用 `extractall()`；
  因此它不是只读本地导入 API。`SetupController.inspect_inputs()` 和
  `prepare_data_sources()` 当前在 GUI 调用路径中同步执行 scan。

结论：保留该服务及其测试，继续只服务旧 Sentinel + ISCE2。新 Reader 不调用
`prepare_inputs()`，也不通过 `extract_zips` 获得 canonical 产品。

#### ResultCatalogService

- `services/result_catalog.py` 扫描 ISCE2 的 `merged/SLC/<date>` 和
  `merged/interferograms/<date>_<date>`，把 `.slc/.int/.cor/.unw` 及 XML/VRT sidecar
  折叠为 `ResultProduct`。
- `ResultProduct.product_id` 由日期、结果 kind、variant 或绝对路径 SHA-1 推导；模型没有
  mission、reader/schema version、source snapshot、普通文件/HDF5 subdataset 资产或
  acquisition layout。
- 它是运行目录的即时输出视图，不持久化输入产品，也不是 Project Data Catalog。

结论：保留 `ResultCatalogService` 和 `ResultProduct` 名称及行为，避免旧 Results 页面回归。
P3 新建 `ProjectDataCatalog`；如果后续统一结果 Catalog，应通过单独 adapter 把
`ResultProduct` 投影为 derived product，不能让当前服务同时承担输入 Catalog。

#### Workbench

- `launch.selected_ui_mode()` 只有在 `INSAR_PILOT_WORKBENCH=1` 时返回 `workbench`；默认
  仍创建旧 `MainWindow`。
- `WorkbenchWindow` 当前中央区只有 `SearchWorkspace`，右侧 Inspector 和底部
  Tasks/Logs dock 默认隐藏；没有 Project/Data Workspace、本地导入或 processing 入口。
- `SearchPresenter` 从生产 Registry 的 descriptor 投影表单，构造 `SearchRequest`，并用
  `remote_product_id` 同步表格、地图和 Inspector。选择产品不会调用 visualization。

结论：当前 Workbench 搜索行为是回归基线。P5 增加 Data Workspace 时，本地
`product_id` 与远程 `remote_product_id` 必须使用不同 model/selection space；Reader 和
目录扫描必须在后台，GUI 只接收 domain DTO。

#### 旧 Sentinel-1 + ISCE2 入口

当前必须保持的调用链为：

```text
launch（默认 legacy）
→ MainWindow
→ SetupController
→ InputCatalogService.scan / prepare_inputs
→ StackWorkflowService.build_generate_command
→ stackSentinel.py 生成 run_files
→ RunController / ProcessRunner
→ ResultCatalogService
→ 用户显式 Preview / Export
```

`MainWindow` 在初始化时直接持有 `InputCatalogService`、`StackWorkflowService`、
`ResultCatalogService`、`ProcessRunner` 和四个 controller。`StackWorkflowService` 固定生成
`stackSentinel.py -s/-o/-a/-d/-w/-W/-C/-n/-p`；`RunController` 解析和执行生成的
`run_files`。CLI 的 `generate/run/status` 同样复用 `ProjectStore`、
`StackWorkflowService`、`HeadlessRunner` 和 `ShellCommandBuilder`。P1–P5 不移动、不改名、
不包裹替换这条链；新 eligibility 只能引用它是一个已经可用的 Sentinel recipe/backend。

### 9.3 不能直接扩展为统一模型的 Sentinel/ISCE2 专用类型

| 当前类型/服务 | 专用假设 | 冻结决定 |
|---|---|---|
| `WorkflowConfig` | `stackSentinel.py`、IW swath、EOF/AUX、NESD/ESD、run files | 保留；NISAR 使用未来独立 recipe config/runtime profile |
| `DataDownloadConfig` | ASF Sentinel scene、EOF、DEM 下载和 selected scene IDs | 保留；不能成为 mission-neutral product catalog |
| `SearchCriteria` / `SceneRecord` / `DownloadTask` | Sentinel ASF 字段、SLC ZIP 下载语义 | 只作为旧 adapter 内部模型；新 Search 继续用现有 domain/search 模型 |
| `InputEntry` / `PreparedInputs` / `InputCatalogReport` | 一个产品是 ZIP/SAFE 路径，IPF/AUX，输出文本 manifest | 保留给 ISCE2；不能表达 HDF5 subdataset 或逐项错误 |
| `InputCatalogService` | 识别 SAFE/ZIP、可解压、写 `safe_inputs.txt` | 不改造成 Reader Registry |
| `ProjectWorkspace.slc_dir()` | 输入统一位于 `data/SLC` | 保持旧默认；新 Catalog 可引用项目外只读 URI |
| `ProjectState.steps` / `RunStep` / `RunSubcommand` | `run_files/run_*` 顺序执行模型 | 保留旧 backend 状态；不作为自由 DAG 或 NISAR workflow state |
| `ResultProduct` / `ResultCatalogService` | ISCE2 merged 目录、日期对、平面栅格及 sidecar | 保留旧 Results；不作为输入 `LocalSARProduct` |
| `VisualizationConfig` | 当前 ISCE/GDAL 栅格预览参数和缓存路径 | 保持显式调用；不在导入或 Catalog selection 中自动触发 |

可以复用的是边界模式，而不是上述数据结构：不可变 descriptor、Qt-free application
service、Registry 冲突校验、portable metadata 校验、后台 runner 和 latest-wins 语义。

### 9.4 真实数据只读 characterization

检查方法只读取目录项、ZIP central directory/`manifest.safe`、HDF5 object metadata 和以下
小型 identification dataset；没有解压 ZIP、读取复数影像像元、生成 sidecar 或调用
processing：

```text
/science/LSAR/identification/productType
/science/LSAR/identification/productLevel
/science/LSAR/identification/missionId
/science/LSAR/identification/platformName
/science/LSAR/identification/lookDirection
/science/LSAR/identification/orbitPassDirection
/science/LSAR/identification/absoluteOrbitNumber
/science/LSAR/identification/trackNumber
/science/LSAR/identification/frameNumber
/science/LSAR/identification/zeroDopplerStartTime
/science/LSAR/identification/zeroDopplerEndTime
/science/LSAR/identification/boundingPolygon
/science/LSAR/identification/listOfFrequencies
/science/LSAR/identification/diagnosticModeFlag
```

初始目录指纹使用递归的相对路径、对象类型、文件大小和 `mtime` 生成，不包含读取时可能由
文件系统更新的 `atime`：

| 根目录 | 文件/目录数 | 总文件字节 | 初始 SHA-256 元数据指纹 |
|---|---:|---:|---|
| `YanAnHighway` | 571 / 79 | 40,115,139,477 | `f1269142d5e87664525078955ffe070d38a170e1cad50a9a9ce6393e0160e311` |
| `HKIA_S1` | 111 / 5 | 223,170,117,733 | `bb4d33c03f72531c681d40af0e82a111c41acccaaaa3eed723255a56467a5aca` |
| `golden/nisar` | 377 / 129 | 403,638,425,654 | `85fa2c3dfe369a353f119b361716476d7ec90e4aacd8c64c6cfd174969b40f80` |

Sentinel 输入统计：

| 数据集 | ZIP | 总字节 | 单文件范围 | manifest/IPF | 轻量格式结论 |
|---|---:|---:|---:|---|---|
| `YanAnHighway/data/SLC` | 2 | 8,190,608,089 | 4,028,505,386–4,162,102,703 | 2/2；均为 IPF 003.90 | 均为 S1A IW SLC `1SDV`；每 ZIP 53 members、6 measurement、24 annotation XML |
| `HKIA_S1/SLC` | 51 | 222,928,423,112 | 4,046,687,528–4,752,481,682 | 51/51；003.31×14、003.40×12、003.51×4、003.52×21 | 均为 S1A IW SLC `1SDV`；45–53 members、均 6 measurement、18 或 24 annotation XML |

现有 `InputCatalogService.scan()` 对这两个目录分别返回 2 和 51 个 ZIP entry，且
`aux_required=False`。这证明旧服务可识别样本，不证明它满足统一 Reader、批量逐项失败、
取消或持久化合同。

`golden/nisar` 顶层有 3 个 HDF5：

| 文件角色 | 数量/大小 | identification 与对象元数据 | 判定 |
|---|---|---|---|
| L1 RSLC reference | 1 / 29,032,972,288 bytes | NISAR、RSLC、L1、Descending、Left、track 13、frame 71、orbit 4783；A/B × HH/HV；207 datasets | P2 正样本 |
| L1 RSLC secondary | 1 / 28,290,580,480 bytes | NISAR、RSLC、L1、Descending、Left、track 13、frame 71、orbit 4956；A/B × HH/HV；207 datasets | P2 正样本 |
| L2 GUNW | 1 / 2,483,027,968 bytes | `productType=GUNW`、`productLevel=L2`，只有 `/science/LSAR/GUNW` | 真实错误产品类型样本，必须拒绝为 RSLC |

两景 RSLC 的 frequency A 复数影像形状分别为 `59280×53929` 和 `57760×53928`，
frequency B 分别为 `59280×6742` 和 `57760×6741`，均为 chunked/gzip `complex64`。
本次只访问 dataset 的 shape/dtype/chunks/compression 属性，没有执行影像 dataset 的
`[()]` 或切片读取；每个 RSLC 实际读取的 identification payload 约 2.2 KiB。

`golden/nisar/phase2/product_manifest.json` 将 1,518,338,048-byte
`RIFG_product.h5` 标为 accepted，选择 A/HH、5 range looks、6 azimuth looks；
`validate_rifg.json` 记录 wrapped/coherence/mask 为 `9880×10785`，抽样 26,195 像元中
23,888 个有效；`runconfig_validation.json` 的检查全部通过且只请求 RIFG。这些文件是一次
外部 ISCE3 0.25.12 成功运行的原型证据。当前仓库没有 NISAR Reader、runconfig builder
或 ISCE3 backend，因此不得据此显示 NISAR Run，也不得宣称当前产品已实现 RIFG。

### 9.5 P1 精确接口建议

建议按下列文件边界新增，不移动现有 Sentinel 服务：

```text
src/insar_pilot/domain/local_data/models.py
src/insar_pilot/domain/local_data/errors.py
src/insar_pilot/providers/local/base.py
src/insar_pilot/providers/local/registry.py
tests/test_local_sar_product.py
tests/test_local_reader_registry.py
```

P2 才新增：

```text
src/insar_pilot/providers/local/sentinel1_safe.py
src/insar_pilot/providers/local/nisar_rslc.py
tests/test_sentinel1_safe_reader.py
tests/test_nisar_rslc_reader.py
```

P3 才新增：

```text
src/insar_pilot/application/local_import/service.py
src/insar_pilot/application/local_import/models.py
src/insar_pilot/services/project_data_catalog.py
tests/test_local_import_service.py
tests/test_project_data_catalog.py
```

P1 模型应为 frozen、Qt-free、JSON 可移植；`native_metadata` 只允许 null/bool/number/string、
list 和 string-key mapping，不允许 `Path`、`datetime`、h5py、zipfile 或 provider SDK 对象。
时间在内存中使用带时区 `datetime`，序列化为 UTC ISO-8601。建议合同如下：

```python
@dataclass(frozen=True)
class AssetRef:
    uri: str
    role: str
    subdataset: str | None = None
    media_type: str = "application/octet-stream"
    size_bytes: int | None = None

@dataclass(frozen=True)
class SourceSnapshot:
    source_kind: str  # file / directory
    size_bytes: int | None
    mtime_ns: int
    member_count: int | None = None
    fingerprint: str = ""

@dataclass(frozen=True)
class LocalSARProduct:
    product_id: str
    native_product_id: str
    mission: str
    platform: str
    product_type: str
    acquisition_mode: str
    acquisition_layout: str
    start_time: datetime
    end_time: datetime
    orbit_direction: str | None
    orbit_identity: str | None
    track: int | None
    frame: int | None
    relative_orbit: int | None
    frequency_bands: tuple[str, ...]
    polarizations: tuple[str, ...]
    footprint_wkt: str | None
    assets: tuple[AssetRef, ...]
    native_metadata: Mapping[str, JsonValue]
    reader_id: str
    reader_schema_version: int
    source_snapshot: SourceSnapshot
```

稳定 ID 不读取或 hash 整个 29 GB 文件。Reader 从受验证的 mission-native granule/product ID
生成 `product_id = "<MISSION>:<PRODUCT_TYPE>:<native_product_id>"`；移动同一产品不改变 ID。
URI 和 `SourceSnapshot` 单独用于定位及 stale/changed 判断。同一 ID 但不同内容进入 Catalog 时
必须报告冲突或 changed，不能静默覆盖。文件 snapshot 可使用 size/mtime 加有界容器元数据
fingerprint；SAFE 目录还应记录 member count，并对 manifest 及关键成员的相对路径、size、mtime
生成 fingerprint。这里不得通过 hash 29 GB payload 来换取稳定性。

Reader 边界应显式区分“不是我的格式”“格式损坏”“格式正确但产品类型不允许”：

```python
class ReaderErrorCode(str, Enum):
    UNSUPPORTED_FORMAT = "unsupported_format"
    CORRUPT_CONTAINER = "corrupt_container"
    MISSING_METADATA = "missing_metadata"
    WRONG_PRODUCT_TYPE = "wrong_product_type"
    UNSUPPORTED_PLATFORM = "unsupported_platform"
    IO_ERROR = "io_error"
    CANCELLED = "cancelled"

class CancellationToken(Protocol):
    def is_cancelled(self) -> bool: ...

@dataclass(frozen=True)
class ReaderContext:
    cancellation: CancellationToken
    metadata_read_budget_bytes: int = 1_048_576

@dataclass(frozen=True)
class ProbeResult:
    supported: bool
    confidence: int
    reader_id: str
    detected_product_type: str | None = None
    reason_code: str = ""

class LocalSARProductReader(Protocol):
    descriptor: ReaderDescriptor
    def probe(self, source: AssetRef, context: ReaderContext) -> ProbeResult: ...
    def read(self, source: AssetRef, context: ReaderContext) -> LocalSARProduct: ...
```

`probe()` 只检查 suffix/signature 和最小结构，不能把损坏容器降级成 unsupported 后交给其他
Reader。Registry 按 descriptor priority 执行轻量 probe；零匹配返回 unsupported，单匹配调用
read，多匹配且同 confidence 返回 `reader_conflict`。每次打开 ZIP/HDF5 前后、目录枚举批次间和
读取每个小型 metadata dataset 前检查 cancellation。P2 的 NISAR Reader 必须把
`/science/LSAR/RSLC/swaths/frequency*/<polarization>` 写成 `AssetRef.subdataset`，但绝不把
打开的 `h5py.File` / `Dataset` 放进返回模型。

P3 的 application/persistence 合同建议为：

```python
@dataclass(frozen=True)
class ImportRequest:
    sources: tuple[AssetRef, ...]
    recursive: bool = True
    dry_run: bool = False

@dataclass(frozen=True)
class ImportItemResult:
    source: AssetRef
    status: str  # imported / duplicate / changed / rejected / failed / cancelled
    product: LocalSARProduct | None = None
    error_code: str = ""
    message: str = ""

class LocalImportApplicationService:
    def inspect(self, request: ImportRequest, context: ReaderContext) -> ImportReport: ...
    def commit(self, report: ImportReport, catalog: ProjectDataCatalog) -> ImportCommitReport: ...

class ProjectDataCatalog:
    def list_products(self) -> tuple[LocalSARProduct, ...]: ...
    def get(self, product_id: str) -> LocalSARProduct | None: ...
    def merge(self, products: Iterable[LocalSARProduct]) -> CatalogMergeReport: ...
    def save_atomic(self) -> None: ...
```

`inspect()` 永远不写入；`commit()` 只写项目的 `.insar_pilot/catalog`。空目录和逐项失败返回
结构化 report，不通过一个异常丢失已完成项目。Catalog 的 index/sidecar 带独立
`schema_version`；`ProjectDocument` 只增加小型 `DataCatalogConfig`（相对 index 路径和
版本），并在 P3 同步更新 `ProjectDocument.from_dict`、`ProjectStore._KNOWN_SECTIONS` 和
schema migration。P1/P2 不改 `ProjectDocument`。

### 9.6 测试矩阵

所有可写 fixture 使用 `tmp_path`。真实数据测试标记为 opt-in，默认 CI 不依赖真实目录，
执行前后都比较源目录元数据指纹。

| 场景 | 默认合成测试 | 预期合同 | 真实 opt-in / 性能证据 |
|---|---|---|---|
| Sentinel ZIP | 最小 ZIP，含唯一 `.SAFE/manifest.safe`、annotation 和 measurement 名称 | Reader 只读返回 SLC 产品与 file asset；不解压 | YanAn 2、HKIA 51；核对 IPF、ID、批量统计 |
| Sentinel SAFE | 最小 `.SAFE` 目录及 manifest | 与等价 ZIP 得到相同稳定 product ID；资产 URI 不同 | 若真实样本没有展开 SAFE，只保留合成验收，不在真实目录解压制造样本 |
| NISAR RSLC | 最小 HDF5，identification + A/B/HH/HV dataset | 接受且生成 HDF5 subdataset assets；不读取 image array | 两景 28–29 GB RSLC；记录 dataset/attribute 白名单、耗时与峰值 RSS |
| 损坏文件 | 截断 ZIP、坏 XML、非 HDF5 `.h5`、截断 HDF5、缺 identification/RSLC group | 逐项 `CORRUPT_CONTAINER` 或 `MISSING_METADATA`；批次继续，无 sidecar | 不破坏真实文件；全部使用 `tmp_path` |
| 错误产品类型 | Sentinel GRD manifest；NISAR GSLC/GUNW/RIFG 最小 HDF5 | `WRONG_PRODUCT_TYPE`；GSLC 必须明确写明只支持 RSLC | 顶层真实 GUNW 和 phase2 RIFG 只读验证拒绝；GSLC 用合成 fixture |
| 空目录 | 空 `tmp_path` | completed report，0 candidates，reason=`no_candidates`；零写入 | 不需要真实数据 |
| 重复导入 | 同 URI 两次、同产品复制到不同 URI、相同 ID 但 snapshot 改变 | imported → duplicate；移动/复制保持 ID；内容变化返回 changed/conflict，不静默覆盖 | YanAn 任一 ZIP 在临时 Catalog 中重复引用，不复制源文件 |
| 长路径 | 总长度至少 320 字符的嵌套目录、长产品名和 Unicode | 完整 URI 可往返；ID 不依赖路径长度；错误消息不截断 domain 值 | GUI 截断只在 P5 view 层验证 |
| 大批量 | 1,000 个轻量假 Reader source，混合成功/失败/重复 | 有界内存、确定顺序、逐项结果、无递归栈风险 | HKIA 51 ZIP；记录总耗时、峰值 RSS、每项平均时间 |
| 取消 | 在目录枚举、probe、metadata read、commit 前分别触发 token | 状态 cancelled；未开始项不读取；inspect 零写入；commit 原子，不能留下半个 index | 可在 HKIA 扫描中触发，但不得依靠网络或修改源目录 |
| dry-run/部分失败 | 成功、损坏、错误类型混合 | inspect 返回完整 report 且源/Catalog 均零写入；之后可只 commit 成功项 | P3 必测 |
| Catalog 重开/旧项目 | schema 1 `project.pilot` + 新 sidecar/index | 旧项目无 Catalog 仍可打开；保存/重开产品一致；未知新字段防御性处理 | P3/P6 必测 |

NISAR 真实 characterization 的资源验收建议：Reader 只读取白名单小型 dataset/attribute 和
object metadata；不访问 complex image 值；峰值 RSS 增量目标不超过 256 MiB，且不随 29 GB
文件大小线性增长。阈值若因 HDF5 library cache 需调整，必须在测试报告中记录基线和理由，
不能取消内存门槛。

### 9.7 迁移顺序和回归门槛

1. **P1 domain + Protocol/Registry**：只新增模型、错误、Reader descriptor/protocol、Registry
   及纯单元测试；不 import h5py/Qt，不修改旧服务或 `ProjectDocument`。
2. **P2 两个 Reader**：Sentinel Reader 只读 ZIP/SAFE；NISAR Reader 以 optional dependency
   使用 h5py，只接受 `/science/LSAR/RSLC` + `productType=RSLC`。当前 `pyproject.toml` 没有
   h5py，P2 必须明确新增可选 extra 和缺依赖错误，不能让基础 Sentinel 安装被迫加载 ISCE3。
3. **P3 Import + ProjectDataCatalog**：先实现 `inspect(dry-run)`，再实现项目 metadata 目录的
   原子 commit/恢复和最小 `ProjectDocument` catalog reference migration。旧
   `InputCatalogService`、`ResultCatalogService` 和 workspace layout 原样保留。
4. **P4 Compatibility/Eligibility**：基于 canonical 产品做 Sentinel stack、NISAR pair 和
   cross-mission rejection。Sentinel recipe 指向现有 ISCE2 服务；NISAR backend 标记
   unavailable，不提供 Run。
5. **P5 Workbench Data Workspace**：在后台调用 Import Application Service；新增独立本地
   table model/selection，保持 Search workspace 和默认 legacy launch 行为；无自动 visualization。
6. **P6 回归与真实验收**：临时项目引用 2 + 51 + 2 个源产品，验证 Catalog 重开、重复、
   性能、取消和 compatibility；随后完整运行 lint/type/test、旧 MainWindow/CLI/ISCE2
   characterization 和 GUI 视觉矩阵。

每一步的合并门槛都包括：Search 默认 Registry 仍只有 ASF Sentinel-1；NISAR GSLC 拒绝；
ALOS 无本地导入/处理；`INSAR_PILOT_WORKBENCH` 仍为 opt-in；产品选择、导入和任务状态不触发
visualization；旧 `stackSentinel.py` 命令及 run-file 执行测试不变。

### 9.8 当前缺口与风险清单

| 风险 | 证据/影响 | 下一阶段控制 |
|---|---|---|
| 把远程结果当本地产品 | `RemoteSARProduct` 没有本地资产快照和 Reader provenance | P1 使用独立 `LocalSARProduct` 和 ID space |
| 把旧 Input Catalog 扩成统一 Catalog | 它会写 manifest/可解压，单错误终止整批 | 服务冻结；新 Reader + Import report |
| NISAR 参数污染 `WorkflowConfig` | 当前字段和 command builder 全是 topsStack 语义 | 独立 Recipe/Runtime Profile；P1–P3 不加入 processing 参数 |
| 大 HDF5 意外整幅读取 | 真实 complex dataset 最大约 59,280×53,929×complex64 | metadata budget、白名单、RSS 门槛、禁止返回 h5py 对象 |
| cancellation 只有结果抑制 | 当前 Search pool 无法中断已运行 provider | ReaderContext cooperative token；每个 I/O 边界检查 |
| 同步扫描阻塞旧 GUI | SetupController 直接调用 recursive scan | 不改旧路径；P5 新导入只走后台 application service |
| project 文件膨胀/损坏 | 8 MiB 上限且当前 save 非原子 | 产品放 catalog sidecar/index；P3 原子写和恢复测试 |
| ID 随路径改变或重复覆盖 | 当前 custom result ID 使用 resolved path hash | mission-native ID 与 URI/snapshot 分离；冲突显式化 |
| 产品类型误接受 | 扩展名 `.h5` 不能区分 RSLC、GUNW、GSLC、RIFG | signature + identification + required group 三重校验 |
| 环境依赖分裂 | base/dev 环境无 h5py，`insar` 环境有 h5py 3.16.0 | P2 optional extra、清晰 missing-dependency error、CI 合成 HDF5 job |
| 原型被误报为产品能力 | `phase2` 有 accepted RIFG，但仓库无 backend | 文档/UI 固定 `backend unavailable`，P4 不显示 NISAR Run |
| 结果/输入 Catalog 名称混淆 | 已存在 `ResultCatalogService` 和 `ResultProduct` | 新类固定命名 `ProjectDataCatalog` / `LocalSARProduct` |
| 跨 mission 配对泄漏 | 统一 table 容易让任意两行进入 Pair | P4 application service 首先按 mission/product type 拒绝 |

P0 的历史退出结论保留作为审计记录；当前状态以第 10 节为准。

## 10. P1–P4 后端实施状态与 Backend-first 后续流程（2026-09-04）

### 10.1 已完成

- `LocalSARProduct`、普通文件/HDF5 subdataset `AssetRef`、来源快照和确定性 JSON 序列化；
- `Sentinel1SafeReader` 与 `NisarRslcReader`，NISAR 只接受 RSLC，`h5py` 为可选依赖；
- `LocalImportApplicationService`，支持文件/文件夹、dry-run、逐项错误、重复导入、显式替换和协作取消；
- `ProjectDataCatalog`，sidecar 只写项目 `.insar_pilot/catalog/products`，使用原子替换；
- Sentinel pair/stack 与 NISAR pair 的独立兼容性规则，跨 mission 明确拒绝；
- `WorkflowRecipeDescriptor` / `TaskDescriptor` 与 Registry；Sentinel 指向现有 ISCE2，NISAR
  Recipe 明确 `backend unavailable`，因此不能产生 Run；
- 单步骤 Task Runtime 核心合同：输入资产、参数覆盖、输出/覆盖策略、Backend Registry、取消、
  重试 lineage、JSONL 日志、原子 run record 和中断恢复；
- NISAR Runtime 精确 probe 与模板驱动 RIFG dry-plan；计划生成不执行命令、不创建输出，
  当前 `insar` 环境因缺少 `isce3` 被明确判定 unavailable；
- 未修改旧 `WorkflowConfig`、旧 MainWindow、旧 Sentinel + ISCE2 服务或可视化触发方式。

真实只读 characterization 已读取 YanAn 2 景、HKIA 51 景和两景 28–29 GB NISAR RSLC；
总计 55 个产品，耗时约 0.42 秒、峰值 RSS 约 48 MiB。读取前后源文件路径、大小和 mtime
指纹一致。两景 NISAR 的实际 `boundingPolygon` 是未标注 `Z` 的 lon/lat/height 三元组，
兼容性解析器已据真实数据修正并加回归测试。

验证基线：`pytest` 431 passed；全仓 Ruff 通过；新增/相关 24 个源文件 Mypy 通过；
`git diff --check` 通过。全仓 Mypy 仍有 39 项既有 GUI typing 错误，均不属于本里程碑后端，
不得为了“全绿”混入本阶段修改。

### 10.2 尚未完成

- Catalog 还没有 Web/Workbench 页面；数据导入不能从新界面调用；
- NISAR ISCE3 RIFG 已有环境探测与 runconfig/command dry-plan，但尚无通过探测的 Runtime，
  也尚未接 TaskBackend 执行适配器，所以只能验证输入，不能运行；
- Sentinel 现有 ISCE2 流程尚未适配统一 Runtime/Task 协议，仍由 legacy service 执行；
- Catalog 当前采用独立 sidecar 目录，不写入旧 `project.pilot`；这是保持旧项目兼容的有意边界；
- 远程 NISAR RSLC/ALOS 生产 Search Provider 仍未实现；ALOS 继续 search-only；
- 大批量取消点、sidecar 恢复策略和 Task 单步骤重跑还需要在统一 Runtime 层继续强化。

### 10.3 下一步 prompts（后端优先，暂缓 PySide/Web）

下面每段应按顺序单独执行；不要直接跳到 UI。

#### P5：Task Execution 与 Runtime Profile（核心合同已完成）

```text
核心合同与 fake-backend 验收已完成。后续 Backend adapter 必须复用 TaskRunRequest、
TaskRunRecord、RuntimeProfile、Backend Protocol/Registry、覆盖策略、取消、重试、结构化日志和
原子状态持久化；不得绕开该层另建 GUI 专用运行状态。
```

#### P6：NISAR ISCE3 RIFG Backend

```text
以 golden/nisar/phase2 中已成功的 runconfig、日志和 RIFG 产物为只读证据，继续实现独立
NisarIsce3RifgBackend。environment probe、runconfig builder 和 dry-run command plan 已完成；
下一步先提供通过 probe 的隔离 Runtime，再实现 TaskBackend adapter 与 opt-in 执行；
参数必须来自 NISAR Recipe，不能进入 Sentinel WorkflowConfig。使用两景 RSLC、DEM、共同
frequency/polarization 生成可审计 plan；环境不可用时明确 unavailable。只有在 dry-run、
合成测试和黄金配置差异验收通过后才允许 opt-in 真执行，且永不覆盖黄金目录。
```

#### P7：Sentinel ISCE2 Adapter 与统一 Task 运行

```text
将现有 StackWorkflowService/RunExecutor 包装为 SentinelIsce2Backend adapter，不重写已验证
topsStack 实现。把生成、单 run_file 执行、参数更新、输出目录和覆盖策略投影到 P5 合同；
确保 ESD、burst merge 等 Task 只属于 Sentinel。旧 GUI/CLI 回归必须保持，统一入口与旧入口
对同一配置产生等价 command plan。
```

#### P8：本地 API 与 Web 前端准备

```text
在 Reader/Catalog/Compatibility/Recipe/Task Runtime 上增加进程内 application facade 和
版本化 DTO；随后才选择 FastAPI 等本地 HTTP/SSE 层。API 只返回可序列化数据，不泄漏 h5py、
Qt、provider SDK 或 subprocess 对象；长任务支持 task_id 查询、取消和日志流。先完成 API
contract/openapi 测试，再决定 JupyterLab 风格前端技术栈。本阶段仍不自动打开可视化。
```

#### P9：Web Workbench

```text
后端 P5–P8 全绿后，再实现浏览器 Workbench：默认紧凑布局，Data Catalog、Pair Inspector、
Recipe/Task 参数和运行日志按需展开。Sentinel 与 NISAR 共用 shell、Catalog 和任务状态组件，
但使用不同 Recipe 表单；NISAR backend unavailable 时没有 Run。可视化始终是显式动作。
```

### 10.4 NISAR AOI 生产链更新（2026-09-04）

本节取代 10.1–10.3 中关于“NISAR Runtime/执行尚不可用”的状态描述；旧文字保留为阶段审计记录。

- 独立 `/home/griffin/miniconda3/envs/insar-nisar` 环境已通过探测：ISCE3/NISAR 0.25.17、GDAL 3.13.3；
- 生产 ASF Provider 只接收 NISAR RSLC，支持 AOI、path/frame、A/B、polarization、PR/UR；
- KML 或 EPSG:4326 Polygon Shapefile 可驱动检索；ASF 返回相交的完整 granule URL，openSEPPO 默认通过远程 HDF5 Range 读取直接生成 AOI RSLC 子集，完整 granule 下载为显式备用路径；
- `insar-pilot-nisar run-insar` 显式支持 RIFG、RUNW、GUNW，保留 `run-rifg` 向后兼容；
- 两景真实 RSLC 的 openSEPPO AOI 子集已在 ISCE3 0.25.17 CPU 环境完成 GUNW workflow：总耗时 41.79 秒，中间 RUNW `277×338`，最终 GUNW `140×117`、EPSG:32611；
- 两景真实 Earthdata HTTPS granule 已在不启用完整缓存的情况下远程裁剪，并与本地 golden 子集及其 RIFG/GUNW 数值结果完成对照；详细指标见 `artifacts/nisar-remote-subset-comparison-2026-09-04.json`；
- 当前剩余边界是把这些 Runner 注册进统一 Task Runtime，并接入后续 Web API/Workbench；可视化仍为显式调用，不自动展示。

可重复操作和验收细节见 `nisar-rslc-aoi-workflow.md` 与 `artifacts/nisar-aoi-e2e-2026-09-04.json`。

### 10.5 官方处理路径收敛（2026-09-04）

本节取代 10.2–10.3 中关于 Sentinel adapter 的待办描述：

- 每个 mission/product type 现在只能注册一条 canonical Recipe；
- Sentinel 固定为 `SENTINEL1_TOPS_BURST_IFG_THEN_MERGE`，阶段从官方
  `stackSentinel.py` 生成的 `run_files/run_*` 动态发现，不再静态伪造 ESD、成图和 merge Task；
- NISAR 固定为 `NISAR_ISCE3_INSAR_RUNCONFIG`，dense offsets/rubbersheet 不再作为应用自有
  独立 Task 暴露；它们若启用，由官方 ISCE3 workflow/runconfig 管理；
- `Isce2TopsStackTaskBackend` 已接入统一 TaskBackend 合同，可单独运行一个官方 run file，
  保留批次并行、失败传播、取消和 JSONL 日志；legacy `RunController` 尚待迁移到同一状态存储；
- `NisarIsce3TaskBackend` 已复用现有 `NisarRifgRunner` 接入 `nisar.run_product`，失败的产品验证
  不会被误记为成功；默认 Backend Registry 只注册这两个官方 adapter；
- 已移除执行前自动改写 `config_merge_igram_*` 的行为，避免静默偏离官方处理计划；
- merged SLC 是官方中间/产品输出，但 merged-SLC direct IFG 在 burst seam 处与官方
  burst-IFG-then-merge 不等价，因此不提供为生产策略。

详细依据和当前唯一架构见[官方处理路径与模块边界](official-processing-paths.md)。
