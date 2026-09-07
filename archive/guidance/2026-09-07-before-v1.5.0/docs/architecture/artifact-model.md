# Artifact 与 phase stack

Artifact 是有版本和出处的逻辑成果，不是任意目录或一张预览图。
一个物理 HDF5 的不同 dataset 可对应不同 Artifact；ISCE 文件及 XML/VRT/HDR 等依赖组成可解析闭包。
新内容使用新 ID；路径映射、样式或 QC 重评不改写历史科学内容。

## 当前产品合同待确认

- 配准 SLC stack：按 acquisition 组织的复数数据，保留幅度和每景相位。
- 缠绕干涉相位 stack：按影像对组织，明确 reference/secondary、单视/多视、滤波及相位约定。
- 二者不能混称相同产品；相位 PNG 不能代替原始复数数据。
- 单视/多视和是否滤波为显式科学配置，不在文档重写时设默认或暗改。
- 具体交付选择待用户确认。解缠产品、GUNW 与时序输出不作本阶段必需交付。

## 身份、提交与可用性

记录类型、mission、Run/import 来源、输入 lineage、物理 assets、空间/时间信息和完整性。
先在临时目录复制或 reflink、解析闭包、验证并写 manifest，再原子发布和事务登记。
不能把仍可变化的工作文件或 hard link 当历史成果。

恢复孤立发布须核对 manifest 和执行记录，文件存在不等于成功。
原始导入允许无 creating Run，但必须有来源信息；未知历史不补造。

## 读取与展示

记录可取得的配对/日期、波长、单位、相位/参考约定、look direction、looks、grid、
shape/dtype、nodata、mask/coherence 和 provenance；未知字段显式缺失。
雷达网格不伪装成 EPSG:4326。仅有可核验 geolocation 时提供地图派生。

Layer 注册只读必要元数据；显示按需窗口/采样/瓦片，缓存不替代科学资产。
后处理输入 bundle 只引用标准成果及缺失字段，当前不提供时序计算功能。
