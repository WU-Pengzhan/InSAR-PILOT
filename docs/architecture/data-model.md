# 数据获取：共享基础设施，分别设计传感器流程

共用 AOI、日期、任务队列、Library、认证接口和三种入口：
从选择创建工程、添加兼容工程、仅下载。搜索结果不等于已绑定 processing Dataset。
All 分组查询允许某 provider 失败而其他结果保留。

## Sentinel 先行

当前优先完善 Sentinel-1 ABCD、任务专属筛选、footprint、场景表、选择和下载管理。
沿用原 ASF / DownloadService / aria2c、SLC/EOF 和元数据能力。
SAFE/SLC、轨道、IPF/AUX、IW/burst 兼容性需要在数据准备页形成清晰报告。

AOI 相交检索不等于只传输 AOI burst；不把完整 SLC 下载标成 burst 子集下载。
检索页与准备页通过同一 AOI/数据版本衔接，共同 burst 可处理范围与场景 footprint 区分。
检索端即时分析与本地精确分析的分工，在第一/第二页设计时明确。

## NISAR 后续

保留 RSLC 检索、完整 HDF5 下载和 openSEPPO 远程 Range/AOI 子集能力。
未来用 NISAR 专属检索字段及获取策略，不将它伪装为 Sentinel SAFE/EOF/burst 流程。
Web 的 Range/DEM 准备尚未全部接线；本阶段不新增该流程 UI。

子集身份记录源 granule、frequency/polarization、窗口、AOI、高度范围与 openSEPPO 版本。
优先以已准备 DEM 的可核验高度范围冻结输入；完整下载仍为显式可选方案。

## Library 与来源

产品身份、内容版本和位置分开；工程引用精确版本。外部路径可用，默认不复制巨大原始数据。
处理器需要可写副本时按需 copy/reflink；不能用 hard link 保证隔离。

下载按身份互斥，partial 不能处理，校验后发布。不同内容不静默覆盖。
暂停保留 partial/aria2 状态，继续或重试保留历史尝试。工程删除不连带删除共享源数据。
size/mtime 仅为快速变化检测，强摘要另行记录；执行前后变更不能成为有效 active。
DEM 版本记录源数据、AOI、垂直基准、转换网格和工具版本。凭据留在本机 credential provider。

## 工程内数据统筹设计（2026-09-07）

[新方案](project-lifecycle-layout.md)建议项目新下载默认归 data、全局 Download Only 留 Library、已有数据明确引用或按需复制。当前下载仍使用共享 Library；目标归属字段及多位置发布尚未实施，身份/版本与单份 Job 权威规则保持。

2026-09-07 工程下载归属已实现：新数据校验后发布到工程 data，Download Only 到 Library，既有注册版本明确引用。目标/版本在审核计划中冻结，重试保持原位置；暂停/失败不发布未完成数据。复制已有数据的独立 UI 与便携导出另行处理。见[实施](../handoff/records/2026-09-07-project-p01-release.md)。
