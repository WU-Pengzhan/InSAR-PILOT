> LEGACY / HISTORICAL EVIDENCE. Not an active architecture specification.

# 下一代 Workbench 线框

本文固定 Workbench shell、Search workspace 和下一里程碑 Data workspace 的低保真结构。Search 第一阶段只验证信息层级、布局切换和 Qt Model/View 边界；Data workspace 的实现边界见本文末尾和[Sentinel-1 / NISAR 数据整合里程碑](sentinel-nisar-data-integration.md)。

## Normal（1440 × 900 基准，1366 × 768 可用）

```text
┌ InSAR-PILOT Workbench ───────────────────────────────────────────────┐
│ Search                                                              │
├──────────────────────┬───────────────────────────────────────────────┤
│ Mission              │ Map                                           │
│ Product type         │                                               │
│ Start / End date     │                                               │
│ AOI                  │                                               │
│ [Advanced filters ▸] ├───────────────────────────────────────────────┤
│                      │ Search results                                 │
│ [ Search ]           │ QTableView / QAbstractTableModel               │
└──────────────────────┴───────────────────────────────────────────────┘
```

- 左侧筛选区约占可用宽度的 24%，但不设置 fixed width。
- 地图与结果区约按 58:42 分配高度。
- Inspector、Tasks 和 Logs 默认隐藏，通过 View 菜单打开。
- Advanced filters 默认折叠。

## Maximized

```text
┌ InSAR-PILOT Workbench ─────────────────────────────────────────────────────┐
│ Search                                                                    │
├────────────────────────┬───────────────────────────────────────────────────┤
│ Mission                │ Map                                               │
│ Product type           │                                                   │
│ Start / End date       │                                                   │
│ AOI                    │                                                   │
│ [Advanced filters ▸]   │                                                   │
│                        ├───────────────────────────────────────────────────┤
│ [ Search ]             │ Search results                                    │
└────────────────────────┴───────────────────────────────────────────────────┘
```

- 最大化只增加地图和结果区域，不增加默认信息量。
- 左侧筛选区保持可操作宽度；地图与结果区约按 64:36 分配高度。
- dock 的展开状态不随窗口模式自动改变。

## 状态边界

- 第一阶段只交付静态空状态；Search 按钮仅发出界面意图，不执行查询。
- 表格模型允许后续注入加载、有数据和错误状态，但本阶段不引入 provider 类型。
- Inspector 只预留选择详情位置；Tasks/Logs 只预留抽屉结构。
- 搜索结果、选择、下载或任务状态均不得触发可视化。

## Capability-driven 表单

第四阶段保留相同线框和两套布局，只改变控件数据来源：

- Mission、Product type、Platform 和 Advanced filters 由生产 Provider Registry 动态注入。
- Mission 改变后重建产品、平台和筛选项；Product type 或 Platform 改变后只保留仍受至少一个 schema 支持的条件。
- 不支持的筛选行隐藏；所有 Advanced filters 仍默认折叠。
- 空 Registry 显示“没有可用 Provider”并禁用 Search，不生成占位 mission。
- 上下文改变会取消活动检索并清除旧结果，不会自动发起查询或可视化。

## Data Workspace：Sentinel-1 / NISAR 数据整合里程碑

### Normal

```text
┌ InSAR-PILOT Workbench ───────────────────────────────────────────────┐
│ Data                                                               │
├──────────────────────┬───────────────────────────────────────────────┤
│ Sources              │ Data Catalog                                  │
│                      │                                               │
│ [Add files]          │ Mission · Type · Time · Mode · Status         │
│ [Add folder]         │ QTableView / QAbstractTableModel               │
│                      │                                               │
│ Import summary       ├───────────────────────────────────────────────┤
│ [Advanced ▸]         │ Inspector / Pair compatibility                │
├──────────────────────┴───────────────────────────────────────────────┤
│ Tasks / Errors / Logs（按需展开）                                   │
└──────────────────────────────────────────────────────────────────────┘
```

- Sources 只承担选择输入和显示本次导入摘要，不常驻显示完整文件树。
- Catalog 是主内容；Sentinel-1 与 NISAR 使用同一 Model/View，不为每行创建 QWidget。
- Inspector 只在有选择时出现，native metadata、完整路径和 HDF5 dataset 列表默认折叠。
- Pair compatibility 是显式动作或临时检查结果，不在每次选择变化时执行重型磁盘读取。
- mission-specific Processing 参数不出现在 Data Workspace。

### Maximized

- 只增加 Catalog 可见行数和 Inspector 空间，不增加默认字段或常驻面板。
- Sources 保持可操作宽度，不因长路径推挤 Catalog。
- Inspector 可作为右侧临时 drawer；Tasks/Logs 仍默认收起。

### 状态与交互

- 必须覆盖空、扫描、结果、部分失败、取消、错误、重复导入和 source changed 状态。
- 文件夹扫描、ZIP manifest 解析和 HDF5 元数据读取全部在后台执行，支持取消和 latest-wins。
- NISAR HDF5 只读取轻量 metadata/dataset 描述，不加载完整复数影像。
- 远程 `remote_product_id` 与本地 Catalog `product_id` 是不同 ID 空间，选择模型不得混用。
- 当前没有可用 ISCE3 Backend 时，NISAR 产品只显示数据可用性和未来 Recipe eligibility，不显示可点击 Run。
- Add、Import、selection、pair check 和 task completion 均不触发自动可视化。
