# Sentinel-1：当前优先实现的专业流程

目标是把 ISCE2 TOPS 的用户工作流在 Web 做到位：
检索/下载 → 输入准备 → 参数与官方生成 → 逐步执行 → phase stack 成果与基础 QC。
页面提案见 [Sentinel workbench](sentinel-workbench.md)。

## 当前终点与保留路径

用户要求近期取得 phase stack，具体 SLC/缠绕干涉相位产品待确认。
单视、多视、滤波不是同义产品；不得在语音术语未明确时自行改变参数。
解缠排障与大范围相位评价暂缓，不作当前页面开发先决条件。

当前验证过的官方生成路径为 `stackSentinel.py -W interferogram`。
保留 TOPS 数值顺序：逐 burst 生成干涉图后再合并，不能改成 merged-SLC 相乘。
如用户选择不同目标产品，先核对官方 generator/adapter 能力和输出合同，再决定执行范围。
本轮不修改 generator、run file、科学参数或现有默认终点。

## 已识别的官方阶段

| 阶段标签 | 科学职责 |
|---|---|
| unpack_topo_reference | 参考 SLC 解包与几何 |
| unpack_secondary_slc | Secondary 解包 |
| average_baseline | 基线 |
| extract_burst_overlaps | burst overlap |
| overlap_geo2rdr | overlap 几何映射 |
| overlap_resample | overlap 重采样 |
| pairs_misreg | 配对 ESD/距离错配 |
| timeseries_misreg | 日期级错配 |
| fullBurst_geo2rdr | 完整 burst 几何映射 |
| fullBurst_resample | 完整 burst 配准重采样 |
| extract_stack_valid_region | 公共有效区 |
| merge_reference_secondary_slc | SLC/几何合并 |
| generate_burst_igram | burst 干涉图 |
| merge_burst_igram | 干涉图合并 |
| filter_coherence | 滤波与相干性 |
| unwrap | 解缠；当前后续开发暂缓，已有记录保留 |

该表描述已有正式阶段，不要求当前每个执行都到第 16 步。
顺序与可选阶段来自对应版本官方计划；未知标签显式报兼容问题。
稳定科学 ID 不依赖永久文件编号；页面分组不合并历史。
不虚构第 17 个 geocode 阶段；GIS 展示派生单独标注。

数据准备保留 SAFE/IPF/AUX、EOF、DEM、AOI/IW/burst 和兼容规则。
参数页提供有语义的表单和 run-file 预览；运行页按真实批次记录退出和基础检查。
计算模式依据已验证处理器能力；发现 GPU 不等于具备有效 CUDA 路线。
