# P01｜可选 EOF/整景 DEM｜设计补充与网络评估

日期：2026-09-06。
本次用户指令与范围：认可前版方向，询问是否已可下载；要求 EOF/DEM 统一可勾选，DEM 覆盖完整 SLC 幅宽及相连 frame 并留余量，评估下载安全、可靠性与速度。
阶段：设计补充/评估。前版方向认可；新增工程默认值与方案待评审，产品未实现。
页面任务卡：[P01](../pages/p01-search-download.md)。
上一份记录：[P01 设计落盘](2026-09-06-p01-search-download-design.md)，保留不改写。

## 接受的决定与仍未知的事项

- 用户明确：EOF/DEM 都可勾选；完整 SLC 联合覆盖，不因后续单 burst 使用缩小 DEM；评估更可靠/更快的下载方法。
- “DM”按 DEM 高程数据理解；先前仅文档交付，不代表新版下载功能已完成或真实下载验收。
- 本次建议默认：EOF 开、DEM 关；勾 DEM 后自动执行 COP30 整景联合 + 20 km；支持补充获取、缓存复用及按角色记录状态。
- 20 km 是工程初值，可增大，P02 仍需覆盖检查；不是任何地形都足够的科学保证。COP30 原始高程参考与处理准备分开。
- 网络建议：保留 aria2c，先修文件校验/EOF 匹配/分片身份，再用全局有限并发、统一代理和退避；速度参数尚非大文件基准结论。
- D01 phase stack/looks/滤波不变；不阻挡本页。没有请求科学运行或开发下一页。

## 实际完成

- 新增[EOF/DEM 与网络评估](../../architecture/p01-ancillary-downloads.md)，同步[主设计](../../architecture/p01-search-download.md)、P01/P02 依赖、index/current/migration、五页职责说明及 MkDocs 导航。
- 明确三入口四种 EOF/DEM 组合、未请求状态、完整 SLC 元数据核对、全 IW/frame 联合、测地余量/外扩对齐、源缺片与容量边界、失败和补充获取。
- P02 新增 DEM Library 来源/范围/余量/版本/原高程参考及覆盖报告；高程转换证明与处理适用性仍在 P02，不增加其页面实现。
- 静态核对下载/DEM/EOF/网络/认证/准备代码及现有测试。发现 Web EOF 固定开、DEM 未接线；旧 DEM 只围绕命中 burst 扩展。
- 两个本地探针确认：S1D mission 映射返回 S1A；1 字节假 ZIP 的现有文件分支返回 skipped。只证明对应代码分支，不声称用户既有数据已经损坏。
- 读取 5 份官方文档，设计引用实际来源；限量公开 COP30 Range 测试完成。
- 增加 A17—A24 未来验收要求；未修产品、未安装依赖或修改代理设置。
- 更新前 8 份指导/导航归档：archive/guidance/2026-09-06-before-p01-dem-network/，SHA-256 清单在 manifest.json。

## 验证与证据

证据目录：artifacts/p01-dem-network-2026-09-06/。

- 官方文档：sources.json、aria2/asf/copernicus/gdal 的 HTML/提取文本、cop30-readme.html/txt；均 HTTP 200，未读取凭据。
- 限量命令：Web Python 执行 network_probe.py；从单个公开 COP30 瓦片分 6 次读取不同 4 MiB 区间，总 24 MiB，WSL 直连、requests、无凭据。
- network-probe.json：1/4/8 并发各两次，平均约 1.46/1.48/1.75 MiB/s；各区间 206、Content-Range、长度与 ETag 一致。仅小请求当前链路证据，不是 aria2/ASF/SLC/全 DEM/用户带宽上限测试。
- local-probes.json：在临时目录构造 1 字节文件调用 DownloadService._download_slc 的已有文件分支；用 Sentinel-1D SceneRecord 调用 OrbitDownloadService._mission，分别为 skipped 和 S1A。临时目录已自动清理，无用户科学输入。
- Web Python 执行 python -m mkdocs build --strict --site-dir /tmp/insar-pilot-p01-dem-network-docs：通过，退出码 0，日志 mkdocs-build.log。
- python3 artifacts/p01-dem-network-2026-09-06/verify_docs.py：通过；9 份文档 82 条本地链接、8 份归档摘要、365 份产品/测试/脚本/配置文件保持一致、新增 8 项验收条目和构建 HTML 检查通过。结果见 validation.json；git diff --check 通过，见 git-diff-check.log。
- 未执行软件完整测试套件、Web UI/E2E、真实 ASF SLC/EOF 下载、DEM 拼接/高程转换、带宽饱和测试或科学计算。A01—A24 不能当作本轮已验收。
- 产品文件快照为 product-baseline.json；科学参数、历史任务/成果与用户输入未修改。

## 服务与任务

- 未启动/停止用户 Web、下载 worker、科学 worker 或浏览器测试服务。
- 公共网络评估是独立短命 Python 进程，仅使用公开数据，不进入产品队列；已结束。读取的栅格字节未作为产品发布或保存完整 DEM。
- 开始时 launcher --status 为 RUNNING，下载/处理任务/worker 都是 0；最终只读检查 2026-09-06T09:59:39+08:00：RUNNING — 0 download jobs, 0 processing jobs, 0 worker processes. 用户服务未操作，继续运行。
- 文档构建仅使用独立 /tmp/insar-pilot-p01-dem-network-docs/；无本次占用端口和持续后台进程。
- 不记录凭据、token、代理秘密或用户数据内容。

## 下一步

- 先读 AGENTS、index/current、P01 卡、主设计与本补充。
- P01 后续实现先处理 EOF ABCD 正确匹配、已有/新 SLC 完整性与发布门禁、Range 对象身份，再补勾选计划、整景 DEM 规划与 Web 接线，最后全局调度和定向验收。
- 吞吐默认值仅在后续授权的 ASF 大文件/稳定区间对照后调整；本次不承诺跑满带宽。
- index/current/P01/migration 已接续本记录；P02 仅登记 DEM 边界和依赖，仍待设计；不自动推进 P03—P05。
