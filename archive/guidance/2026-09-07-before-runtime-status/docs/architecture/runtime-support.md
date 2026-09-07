# Web 与科学运行环境兼容合同
日期：2026-09-07。状态：用户要求已确认；当前实现缺口列于下文，不能当作全部交付。

## 用户要求与能力边界
- 用户可能使用 Conda，也可能不使用。Web 启动不要求手动激活 Conda；这不等于 ISCE2/ISCE3 已安装，也不等于 Web Python 完全不依赖任何 Conda 基础 Python。
- 应用 Python、ISCE2 TOPS Python、ISCE3 NISAR Python 是三个独立配置。两种 ISCE 不要求装进同一个环境，不按环境名称硬编码。
- 完整科学安装必须分别证明 ISCE2 与 ISCE3 工作流可用；不能仅检查 Web 导入或发现 python/nvidia-smi。
- 缺处理器时仍可使用不依赖该处理器的功能，例如检索下载；Sentinel 运行需 ISCE2，NISAR 运行需 ISCE3。缺 ISCE3 不应阻断 Sentinel。
- 下载自己的 aria2/GDAL/认证依赖也需单独检查。ISCE3 导入成功不证明 openSEPPO 子集策略可用。

## 支持路径
| 用户环境 | 接入合同 | 当前验收状态 |
|---|---|---|
| 已有 Conda/Mamba 科学环境 | 用户选实际 Python/工具路径，以独立子进程执行；检测版本、依赖与官方入口 | 本机有既有科学证据，本轮只重新检查模块导入 |
| 不用 Conda，但已有系统/源码安装 | 用户选 Python、TOPS 工具、必要库/数据目录；不能假设 conda-meta 或固定 share 布局 | 目标必须支持；现有 adapter 的 Conda 假设仍待消除并验收 |
| 未安装科学处理器 | 安装向导分别提供两种处理器的可复现安装/修复路径，安装后重新检查 | 尚无完成验收的跨环境一键安装器，不能宣称已自动安装 |

可推荐受控 Mamba/Micromamba 环境降低安装难度，但它们仍属 Conda 包生态，不能作为“完全非 Conda 路径已验收”的证据。
依赖应遵循官方处理器安装合同；不能承诺 pip install isce2/isce3 即可得到完整工作流。

## 运行前检查合同
1. 对选中的实际解释器建立干净、明确的执行环境，检查失效链接、权限、Python 与库兼容性。
2. Sentinel：导入 ISCE2/isceobj，核验 topsStack 官方工具入口、GDAL/PROJ；按选中步骤检查额外工具，解缠未启用时不把 SNAPHU 当作当前 phase-stack 的无条件门禁。
3. NISAR：导入 ISCE3、nisar.workflows.insar，核验 GDAL HDF5 驱动/PROJ，保留模板和科学开关合同。
4. CPU/CUDA 分别报告，显式 CUDA 不满足时阻断；发现显卡不代表处理器支持 CUDA。
5. 计划预览与实际运行前均重新核验所需能力。配置可保存为未验证，不能因此允许科学执行。版本/路径变化使旧观察失效。
6. 报告安装方式、实际解释器、版本、缺失项和修复入口；冻结实际 runtime provenance。凭据不进入报告。

## 本轮核对的实际缺口
- application/engine_processing.py::runtime_environment 直接设置 CONDA_PREFIX，并推导 prefix/share/proj、share/gdal、share/isce2/topsStack；不是通用非 Conda 执行合同。
- infrastructure/engine_fingerprint.py 主要记录 Python 文件与 conda-meta；缺少非 Conda 处理器/依赖版本证明。
- /compute/profiles 保存 observation 使用 fingerprint，不能据此认为已经执行完整能力探测。
- 已有 NisarIsce3RuntimeProbe 可复用，但应统一到与实际 Job 一致的环境解析和运行前检查中。
- 本机 Web venv 已摆脱 /tmp，但基础 Python 仍来自持久 insar Conda 环境；只是启动时无需 activate，不是无 Conda 安装验证。
- 当前 environment.yml 与 scripts/verify_install.py 偏旧 Qt/ISCE2 路线；不能作为两种科学处理器均已就绪的新版安装合同。

## 后续实施与验收
共享安装/runtime 工作独立于 NISAR 新 UI，不需要同时重做两条科学页面。
先实现统一环境解析与结构化 probe，然后接入配置、计划/运行门禁，最后提供安装/修复交互。
验收覆盖：Conda 2/3、非 Conda 系统或源码 2/3、完全未安装、只安装一方、失效解释器、错误库/PROJ、CPU/CUDA 分离；相应真实官方最小调用单独留证。
本轮没有改变数值代码或安装处理器；模块导入结果不是重新完成科学流程或 CUDA 验收。
