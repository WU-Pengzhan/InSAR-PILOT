# 工程与数据绑定

一个工程固定一个 sensor/mission Profile。Sentinel-1 A/B/C/D 属于同一个 Sentinel-1 TOPS Profile，不要求每颗卫星建立独立界面。

未分配工程可搜索和编辑 AOI。首次正式绑定 processing Dataset 时，在同一次修订中锁定 Profile。
轨道和 DEM 不决定 Profile；删除全部影像也不自动解锁。需要另一 mission 时创建另一工程。
All 检索可混合显示，绑定前必须按 mission 分组。

Sentinel Dataset 支持多景 stack，记录参考影像与选择条件。
NISAR 数据可收藏多景；现有处理合同为每个 Pipeline 一对兼容 RSLC、一个 frequency/polarization，后续阶段再完善专属交互。

## 工程意图与历史

`project.pilot` 保存可读 JSON：ID、schema、名称、Profile、AOI、数据引用、期望配置和流程版本。
SQLite 保存接受的修订和运行历史。应用偏好不混进科学签名。

修改经过修订检查、单写者、pending 记录、原子替换和接受修订提交。
恢复完成前不提交新任务；手动改文件须校验后导入新修订，不能绕开 Profile 锁定或改写历史。

## 页面配合与导入

“数据与准备”负责场景/目录、输入角色和参考影像；“参数与生成”消费同一修订并冻结具体执行参数。
页面返回修改必须显示影响，不另存相互冲突的参考影像或 DEM 设置。

旧工程导入为新 ID、新目录，保留原配置、来源和可核验成果。
缺失命令、参数和环境保持未知；旧 success 标志不能直接变成新成功 Run。
旧 Qt 界面停止开发，不改变对源数据与历史证据的保护。
