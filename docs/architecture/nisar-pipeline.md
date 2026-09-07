# NISAR：保留能力，后续单独推进

当前开发先聚焦 Sentinel。NISAR/ISCE3/openSEPPO 代码、模板与数据证据保留；
不为了界面统一而把 NISAR 改造成 TOPS 步骤，也不在这一轮新增全部 NISAR 页面。

一个 NISAR 工程锁定 NISAR Profile。现有每个 Pipeline 处理一对兼容 RSLC 与一个 frequency/polarization。
后续可采用与 Sentinel 不同的准备、参数和运行视图；只共享工程/Job/Artifact 等基础设施。

## 后续编排边界

RSLC 兼容检查 → DEM 准备 → 完整 RSLC 或 openSEPPO AOI/Range 子集 →
版本匹配 runconfig → 官方 `python -m nisar.workflows.insar` → 实际产品登记。
这描述后续设计范围，不能宣称 Web 已接通所有准备操作。

RIFG/RUNW/GUNW 是目标产品合同，不假定三次独立串联执行。
近期 phase stack 的 NISAR 对应交付在其专属设计阶段确认，不自动要求 RUNW/GUNW。
内部 geometry、resampling、crossmul、unwrap、geocode、correction 等阶段来自模板开关与真实事件，
用于观察，不默认单独调度或中断恢复。

## 科学与数据保护

不改变已有模板科学设置、校正项、频段/极化或官方算法。
源 RSLC 只读；子集记录 granule、窗口、高度范围、版本和来源。
Range 子集与完整 HDF5 下载是不同获取策略，不能套用 Sentinel burst 下载概念。

已有 CPU 数值证据保留，部分环境敏感性未定位；完整相位/GUNW 对照与 CUDA 本阶段暂缓。
未支持或未验证模式明确说明，不静默回退，不把历史差异改写成通过。
