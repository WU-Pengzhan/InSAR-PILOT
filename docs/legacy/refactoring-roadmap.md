> LEGACY / HISTORICAL EVIDENCE. Not an active architecture specification.

# 下一代重构路线与 GUI 设计约束

本文定义 InSAR-PILOT 下一代工作的目标边界、GUI 设计硬约束和实施顺序。它是面向开发者的目标规范，不描述当前 v1.2.0 已经交付的功能。当前版本的真实行为仍以[用户手册](../user-guide.md)和[架构说明](architecture.md)为准。

## 0. 当前状态与活动里程碑

Workbench shell、统一搜索领域层、Capability-driven 表单和 Sentinel-1 远程检索接入已经形成下一阶段开发基线。生产 Registry 当前仍只有 ASF Sentinel-1；NISAR RSLC 和 ALOS search-only 仍停留在领域契约和 fake-provider 测试。

当前活动里程碑改为：**Sentinel-1 / NISAR 数据整合完成**。其详细边界、真实数据路径、Task 适用性规则、验收条件和可直接用于 VSCode Codex 的顺序化 prompts 见[Sentinel-1 / NISAR 数据整合里程碑](sentinel-nisar-data-integration.md)。

本里程碑中的“整合”表示统一逻辑产品、资产引用、本地导入、Data Catalog、兼容性和 Workflow Eligibility，不表示 Sentinel-1 与 NISAR 可以组成跨 mission 干涉对，也不表示 NISAR ISCE3 RIFG/RUNW/GUNW 已经完成。

## 1. 重构原则

重构采用增量方式，不在一个版本中同时替换 GUI、数据模型和 ISCE2 工作流。

- 当前已经工作的 Sentinel-1 + ISCE2 TOPS Stack 流程必须保留。
- 新 GUI 先以独立 Workbench shell 搭建，在通过视觉和交互验收前不替换现有主窗口。
- GUI 只调用 Application、Search、Task 和 Backend 接口，不直接拼接处理命令。
- 数据先统一为逻辑产品和资产引用，不强制转换成统一物理文件格式。
- 可视化是用户显式调用的功能，不是产品导入、任务完成或产品选择后的默认动作。
- 新模块必须有清晰的当前范围；不为尚未计划支持的处理链预建大量空实现。

## 2. 已完成检索阶段的任务范围（历史基线）

### 2.1 Mission 范围

| Mission | 下一阶段目标 | 明确不包含 |
|---|---|---|
| Sentinel-1A/B/C/D | SLC 数据检索；统一检索结果；为后续导入和现有 ISCE2 流程保留接口 | 不在检索重构阶段重写现有 ISCE2 处理链 |
| NISAR | RSLC 数据检索和统一结果模型 | GSLC；本阶段的完整 InSAR 处理接入 |
| ALOS 系列 | 仅完成检索层接入和结果展示 | SLC 统一导入、ISCE2/ISCE3 处理和 InSAR workflow |

Sentinel-1D 必须作为显式 platform 处理。若上游 provider 或当前依赖版本尚未提供对应枚举，界面应返回明确的“provider 暂不支持”状态，不能静默退化为不受约束的 Sentinel-1 全平台检索。

ALOS 的具体卫星、产品级别和 provider 能力需要在实现前形成独立支持矩阵。没有经过验证的产品类型不得仅凭名称映射为可处理 SLC。

### 2.2 产品和可视化范围

统一产品模型需要能够表达 TOPS、Stripmap 和 ScanSAR SLC，但下一阶段只要求 Sentinel-1 SLC 和 NISAR RSLC adapter 所需的字段落地。模式差异放在 acquisition layout、swath、segment 和 native metadata 中，不把所有 mission 字段堆入一个扁平模型。

可视化作为独立服务按需调用：

```text
用户选择产品
→ 选择“可视化”功能
→ 选择 renderer 和参数
→ 创建可取消的可视化 Task
→ 生成临时预览或显式导出
```

产品导入、搜索结果选择和处理任务完成后均不得自动生成预览。后续 renderer 可以覆盖 SLC、IFG、UNW、COH 和雷达几何资产，但不属于下一阶段“框架 + 数据检索”验收范围。

## 3. 首版 GUI 反馈与重设计目标

首版用户反馈集中在两个方面：信息密度过高，以及交互和缩放不流畅。下一代 GUI 不复用当前页面的信息组织方式，只复用已经验证的业务服务。

### 3.1 信息层级

默认界面只展示完成当前操作所需的信息。

- 一个页面只保留一个主要任务和一个主要动作。
- 主要按钮每个工作区原则上不超过两个；次要动作放入菜单或 overflow。
- 长文字提示改为短标签、状态图标、tooltip 和按需帮助。
- 路径、命令、provider 原始响应、诊断详情和完整日志默认折叠。
- Advanced filters、Technical details 和 Logs 必须按需展开。
- 空状态用于解释下一步，不在正常状态下持续占用大面积空间。
- 相同状态只展示一次，禁止同时出现在 toolbar、card、sidebar 和正文。

### 3.2 工作台信息架构

下一阶段只实现项目和数据检索所需的最小工作台：

```text
┌ Project / Search / Download / Task status ┐
├──────────────┬─────────────────────────────┤
│ Search       │ Map                         │
│ Filters      │                             │
│              ├─────────────────────────────┤
│              │ Search Results              │
├──────────────┴─────────────────────────────┤
│ Tasks / Errors / Logs（按需展开）          │
└────────────────────────────────────────────┘
```

- Search Filters 只显示 mission、product type、date、AOI 和最常用筛选项。
- 轨道、极化、频段、provider-specific 选项放入 Advanced filters。
- 地图和结果表是主要内容；单个产品详情采用抽屉或右侧临时 inspector。
- Task/Log 面板默认收起，仅在运行、失败或用户主动打开时出现。
- 下一阶段不加入 Processing Setup、自由 DAG、常驻 Results 页面或默认可视化区域。

### 3.3 尺寸与布局策略

只维护两套经过视觉验收的布局策略，而不是让每个 widget 独立决定固定尺寸或拉伸行为。

1. **Normal layout**：以 1440 × 900 为设计基准，并保证 1366 × 768 可用。
2. **Maximized layout**：使用可用屏幕空间，增加地图和结果区域，不增加默认信息量。

窗口在两种策略之间变化时通过统一 breakpoint 切换布局。禁止在各页面散布基于当前宽度的临时判断。

尺寸规则：

- 只有图标、状态点和少数基础控件可以使用固定尺寸。
- 页面、列表、地图、表格和 inspector 使用统一 `QSizePolicy`、minimum size 和 stretch factor。
- 禁止同时对父容器和主要子组件设置互相冲突的 fixed width/height。
- 可隐藏低优先级区域，但不得通过挤压使按钮、输入框或表头不可操作。
- splitter 比例和 dock 状态由 layout controller 管理，不由各 feature 自行保存。
- Normal 和 Maximized 两种状态都必须在 100%、125% 和 150% DPI 下检查。

### 3.4 点击、拖拽和滚动体验

- 常用点击目标的最小有效高度为 36 px；紧凑表格行不得低于 28 px。
- splitter handle 和滚动条必须有可稳定拖拽的命中区域。
- 滚轮事件只由光标所在的主要滚动容器处理；ComboBox 和 SpinBox 未获得明确焦点时不得截获页面滚轮。
- 地图缩放、列表滚动和 splitter 拖动期间不得同步执行网络、磁盘扫描或全量模型重建。
- 高频鼠标和滚轮事件必须 throttle/coalesce；搜索结果和地图 marker 使用批量更新。
- 大型结果集使用 Qt Model/View，不使用为每个单元格创建 QWidget 的实现。
- 主线程不得解析大型 SAFE/HDF5、生成 quicklook、下载数据或执行 GDAL/ISCE 命令。
- 动画只用于短时状态过渡；当它影响滚动或窗口调整时应关闭。

### 3.5 视觉检查是合并门槛

GUI 功能在编码前先提交低保真 wireframe；实现后必须生成并检查截图。仅有 offscreen widget 单元测试不代表界面验收完成。

每个主要页面至少检查：

- Normal、Maximized；
- 100%、125%、150% DPI；
- 中文和英文；
- 空状态、加载状态、有数据状态、错误状态；
- 长路径、长产品名和长错误信息；
- dock 展开/收起、窗口最大化/恢复；
- 无遮挡、无截断、无组件重叠、无不可点击控件。

涉及滚动、地图或大型结果表的改动还需人工验证连续滚动、拖动和缩放期间没有明显停顿。发现视觉问题时先修复布局和 event handling，不通过继续增加提示文字解决。

## 4. 新框架边界

下一阶段采用以下最小分层：

```text
GUI Workbench
    ↓
Search Application Service
    ↓
Mission-neutral SearchRequest / RemoteSARProduct
    ↓
Provider Registry
    ├── ASF Sentinel-1 Provider
    ├── NISAR Provider Adapter
    └── ALOS Provider Adapter

GUI Workbench
    ↓
Task Application Service
    ↓
SearchTask / DownloadTask / Cancellation / Events
```

### 4.1 统一检索接口

```python
class SARSearchProvider(Protocol):
    descriptor: ProviderDescriptor

    def supports(self, request: SearchRequest) -> SupportReport: ...
    def search(self, request: SearchRequest, context: SearchContext) -> SearchPage: ...
```

统一请求只包含跨 mission 可比较的字段：

```text
mission
platforms
product_type
start_time / end_time
AOI
orbit_direction
relative_orbit
polarizations
frequency_bands
page / page_size
```

provider-specific 条件放在 namespaced options 中，不进入 GUI 的默认表单。

统一结果：

```text
remote_product_id
provider_id
mission / platform
product_type
acquisition_time
orbit metadata
polarizations / frequency bands
footprint
size
download capability
provider metadata
```

RemoteSARProduct 是远程检索结果，不等于已经导入项目 Catalog 的 SLCProduct。

### 4.2 GUI 与搜索服务解耦

- GUI 不 import ASF/NASA provider SDK 类型。
- GUI model 只接收 `RemoteSARProduct` 和 `SearchPage`。
- provider 错误转换为统一错误类型：认证、网络、限流、不支持、查询无效和 provider 故障。
- 搜索可取消；旧请求返回时不能覆盖较新的查询结果。
- 地图 marker 和表格行共享相同 product ID 和 selection model。
- 搜索历史和 cache 不直接写在 QWidget 中。

## 5. 检索阶段实施顺序（历史基线）

### Step 0：冻结现有流程

- 保持现有 327 项测试和 85% coverage 门槛。
- 为当前 Sentinel-1 ASF 查询建立 characterization tests。
- 不移动 `StackWorkflowService`、`ProcessRunner` 或现有 ISCE2 页面。

### Step 1：GUI wireframe 和交互原型

- 先完成 Normal/Maximized 两套静态原型。
- 用真实长度的中文、英文、路径和产品名检查布局。
- 明确 Search、Map、Results、Inspector、Task drawer 的显示规则。
- 原型通过评审后再建立 Qt widgets。

### Step 2：框架骨架

建议新增而非重写现有目录：

```text
src/insar_pilot/application/search/
src/insar_pilot/application/task/
src/insar_pilot/domain/search/
src/insar_pilot/providers/sar/
src/insar_pilot/ui/workbench/
src/insar_pilot/ui/models/
src/insar_pilot/ui/features/search/
```

新 Workbench 通过开发开关启动。通过验收前，默认入口继续打开现有 GUI。

### Step 3：统一检索模型和 Provider Registry

- 定义 `SearchRequest`、`RemoteSARProduct`、`SearchPage`、`SupportReport`。
- 将现有 ASF Sentinel-1 provider 包装到新接口，不复制搜索逻辑。
- 增加 Sentinel-1A/B/C/D 显式 platform 映射和测试。
- 增加 NISAR RSLC 搜索 adapter；界面和 service 层拒绝 GSLC。
- 增加 ALOS 检索 adapter，但不注册 processing capability。

### Step 4：数据检索工作区

- 使用 `QAbstractTableModel` 展示结果。
- 地图与结果表共享 selection；marker 批量更新。
- Advanced filters、Inspector、Task/Log drawer 默认折叠。
- 支持取消、重新检索、分页或受控 result limit、明确错误状态。

### Step 5：视觉、交互和回归验收

- 执行第 3.5 节的截图矩阵。
- 真实检索请求不阻塞主线程。
- 快速滚动、地图缩放和 splitter 拖动期间无明显卡顿。
- 旧 GUI 和 Sentinel-1 + ISCE2 流程仍可启动并通过测试。

## 6. 检索阶段验收基线

“框架搭建以及数据检索做到位”只有同时满足以下条件才算完成：

1. 新 Workbench shell 不依赖现有 `MainWindow` 控件别名或 controller 对 window 的直接访问。
2. Sentinel-1A/B/C/D、NISAR RSLC 和 ALOS 通过统一 `SearchRequest` 发起检索。
3. NISAR GSLC 不出现在可选产品中，并在 API 层被明确拒绝。
4. ALOS 结果没有 Run/Process 入口，Catalog 中也不声明 processing capability。
5. provider 原生对象不会进入 GUI；所有结果转换为 `RemoteSARProduct`。
6. 搜索可取消，过期请求不能覆盖最新结果。
7. 地图、结果表和详情选择保持同步。
8. 可视化不会因搜索、选择、下载或任务完成自动运行。
9. Normal/Maximized 与 DPI/语言视觉检查全部通过。
10. 当前测试、lint、type check 和现有 ISCE2 工作流保持可用。

完成该阶段后，再进入下载统一、Canonical SLC/RSLC 导入、Data Catalog 和 Backend 重构。不要在数据检索阶段同时实施这些后续模块。

## 7. Capability-driven Search Framework

第四阶段先稳定 provider 能力契约，再接入新的生产 provider：

- `SearchCapability` 描述 mission、产品类型、平台、跨 mission 筛选项和分页限制。
- `ProviderDescriptor` 继续描述 provider 自身的 SEARCH/DOWNLOAD/PROCESSING；Search Registry 不承担处理 Backend 职责。
- Workbench 表单不得持有 Sentinel、NISAR 或 ALOS 选项列表，所有选项均由生产 Registry 经 Application Service 投影。
- 不受 descriptor 支持的组合在后台任务提交前失败；provider 的运行时可用性仍由后台 `supports` 检查。
- 本阶段生产 Registry 仍只有 ASF Sentinel-1。NISAR RSLC 和 ALOS search-only 用 fake provider 验证，不以占位 adapter 进入生产环境。

分页能力进入 schema 与请求校验，但翻页控件、下载、Catalog、导入、处理和可视化仍不属于本阶段。

## 8. 当前活动里程碑：Sentinel-1 / NISAR 数据整合

检索阶段之后的开发不直接跳到完整 ISCE3 处理，而是先稳定本地数据合同：

```text
Sentinel ZIP/SAFE ─→ Sentinel1SafeReader ─┐
                                          ├→ LocalSARProduct / AssetRef
NISAR RSLC HDF5 ─→ NisarRslcReader ──────┘
                                                      ↓
                                               Project Data Catalog
                                                      ↓
                                      Compatibility / Workflow Eligibility
```

活动里程碑必须做到：

- 原始数据只读，不强制物理格式转换；
- 普通文件与 HDF5 subdataset 都可作为资产引用；
- 同一 Catalog 可检查 Sentinel-1 SLC 和 NISAR RSLC；
- Sentinel stack、NISAR pair 和跨 mission 不兼容关系由 Qt-free service 判断；
- Sentinel TOPS Task 与 NISAR Task 由 Recipe/Capability 投影，不在 GUI 中硬编码；
- 当前没有可运行 ISCE3 Backend 时，不显示虚假的 NISAR Run 入口；
- 数据选择、导入和任务状态均不触发自动可视化；
- 现有 Sentinel-1 + ISCE2 和 Workbench 搜索基线保持可用。

该里程碑完成后，下一里程碑才是基于黄金 RSLC/RIFG 样本重建独立 Runtime Profile 和 NISAR ISCE3 RIFG Backend。完整实施与 prompt 顺序以[专项文档](sentinel-nisar-data-integration.md)为准。

截至 2026-09-04，Qt-free 的 Reader、统一产品、Import/Catalog、Pair Compatibility、
Workflow Eligibility（专项文档 P1–P4）和 Task Runtime 核心合同已完成验收；NISAR 已完成
Runtime probe 与模板驱动 RIFG dry-plan。当前按 backend-first 路线继续：先提供通过 probe 的
ISCE3 Runtime 和 NISAR TaskBackend，再实现 Sentinel legacy adapter，最后提供本地 API 与
Web Workbench；现阶段不继续扩展 PySide 页面。
