# NISAR RSLC：AOI 检索、下载、子集化与 ISCE3 InSAR

> 既有能力与实验记录：当前先开发 Sentinel Web，NISAR/openSEPPO 保留并后续推进。本文旧 GUI/环境描述仅反映记录时状态，不是当前页面开发任务；见 [当前架构](architecture/overview.md)。

本文记录当前可用的无 Qt 后端链路。GUI/Web 前端后续只需调用同一 Application Service；检索、认证、下载、openSEPPO 子集化和 ISCE3 执行均不依赖 QWidget。

## 1. 能力边界

```text
KML / EPSG:4326 Shapefile
        ↓
AOI WKT
        ↓
ASF NISAR Provider（RSLC only）
        ↓
Acquisition manifest（JSON，无账号或口令）
        ↓
openSEPPO 远程 HDF5 Range 读取
        ↓
AOI radar-grid subset（新的本地 RSLC HDF5）
        ↓
ISCE3 NISAR RIFG / RUNW / GUNW workflow
        ↓
HDF5 product contract validation
```

ASF 的 AOI 参数用于选择 footprint 与 AOI 相交的完整 NISAR frame/granule。ASF Data Search 返回完整 HDF5 URL，并不在服务端生成裁剪产品；openSEPPO 随后通过 HTTPS/S3 Range 请求和 HDF5 page/block cache 读取 granule 中需要的数据，在本地构造可被 ISCE3 读取的 RSLC 子集。因此主路径不需要预先下载完整的 28–29 GiB granule。完整下载只作为离线复用或远程分块读取失败时的显式备用路径。

Shapefile 必须是 Polygon，坐标系为 WGS84 geographic / EPSG:4326。单一 ring 保留原形状；多 feature/part 会用共同包络矩形查询，以确保不漏掉任何 feature，同时可能带来少量额外 granule。

## 2. 运行环境

GUI 继续使用 `/home/griffin/miniconda3/envs/insar`。NISAR 处理使用独立环境，避免 ISCE2/PySide 与新版 ISCE3 的二进制依赖相互覆盖：

```bash
/home/griffin/miniconda3/envs/insar/bin/python -m insar_pilot.cli.nisar \
  probe-runtime \
  --python /home/griffin/miniconda3/envs/insar-nisar/bin/python
```

当前已验证的 runtime 是 ISCE3 0.25.17、GDAL 3.13.3，并包含 `libgdal-hdf5`、`pyaps3`、`snaphu`、openSEPPO 0.7.1。Backend 会为该 Python 自动推导同环境的 `share/proj`；也可以显式传入 `--proj-data`。

## 3. AOI 检索

```bash
/home/griffin/miniconda3/envs/insar/bin/python -m insar_pilot.cli.nisar search \
  --aoi docs/examples/nisar-aoi-example.kml \
  --start 2026-06-26 \
  --end 2026-07-10 \
  --direction DESCENDING \
  --path 13 \
  --frame 71 \
  --frequency A \
  --polarization HH \
  --production-configuration PR \
  --limit 20 \
  --manifest /tmp/nisar-search.json
```

Manifest 保存规范化 product ID、时间、path/frame、A/B frequency、polarization、footprint、字节数与下载 URL；不保存 provider SDK 对象或认证信息。

## 4. 认证与下载

不要把口令放在命令行参数、脚本、项目 JSON 或 Git 文件中。建议只在当前 shell 临时设置，或使用权限为 `0600` 的 `~/.netrc`：

```bash
read -r -p "Earthdata username: " EARTHDATA_USERNAME
read -rs -p "Earthdata password: " EARTHDATA_PASSWORD
export EARTHDATA_USERNAME EARTHDATA_PASSWORD
```

先进行 8 字节 HDF5 signature 探测：

```bash
/home/griffin/miniconda3/envs/insar/bin/python -m insar_pilot.cli.nisar \
  probe-download --manifest /tmp/nisar-search.json
```

预览完整 granule 下载目标，不写数据：

```bash
/home/griffin/miniconda3/envs/insar/bin/python -m insar_pilot.cli.nisar download \
  --manifest /tmp/nisar-search.json \
  --output /data/nisar-project \
  --dry-run
```

去掉 `--dry-run` 后开始完整 HDF5 下载。下载先写 `*.part`，成功后原子改名；取消或失败保留 partial file，下一次可由 aria2 续传。可重复 `--product GRANULE_ID` 只下载 manifest 中选定的产品。该命令不是 AOI 主路径的必经步骤。

## 5. AOI 子集化

直接根据搜索 manifest 远程读取两个 granule，不添加 `--cache`：

```bash
/home/griffin/miniconda3/envs/insar/bin/python -m insar_pilot.cli.nisar subset \
  --manifest /tmp/nisar-search.json \
  --aoi docs/examples/nisar-aoi-example.kml \
  --output /data/nisar-project/subsets \
  --executable /home/griffin/miniconda3/envs/insar-nisar/bin/seppo_nisar_rslc_convert \
  --frequency A \
  --polarization HH \
  --min-height 0 \
  --max-height 3000
```

`--max-height` 应覆盖 AOI 的最高地形，否则 radar/geo 坐标转换可能裁掉边缘。openSEPPO 0.7.1 在未提供该参数时查询 USGS Elevation Point Query Service 的 AOI 四角和中心，并在最高点上增加 500 m；失败时回退到 1000 m。当前版本的 `--min-height` 不参与像元窗口选择，只作为输出 bounding polygon 四角查询失败时的远距侧回退值。输入始终只读；输出目录必须为空。默认不生成 quicklook，只有显式 `--quicklook` 才可视化。需要审计自动高度和最终窗口时增加 `--verbose`，信息会写入 subset 任务日志。

`--manifest` 中每个 granule URL 会生成一个独立 subset HDF5。也可以重复 `--product GRANULE_ID` 只处理选中的产品，或改用重复 `--input URL`/`--input LOCAL_FILE`。默认不传 openSEPPO 的 `-cache`，因此远程 URL 使用 HDF5 Range 读取；只有显式 `--cache y` 或 `--cache /path` 才会在裁剪前缓存完整 granule。

NISAR subset CLI 的网络模式默认为 `--network-mode direct`，会从 openSEPPO 子进程环境中移除 WSL 的 `HTTP_PROXY`、`HTTPS_PROXY` 和 `ALL_PROXY`（包括小写形式）。只有显式传入 `--network-mode environment` 才继承 WSL 代理。2026-09-04 实测 WSL 环境代理出口为 HK，清除代理后出口为 CN；直连 ASF 检索、Earthdata HTTP 206 Range 和一景 openSEPPO 远程裁剪均成功，裁剪耗时 97.14 秒且输出 SHA-256 与 golden 完全相同。

## 6. ISCE3 处理

ISCE3 runconfig schema 与软件版本强相关，因此 Backend 从一个已验证的 mission template 派生新配置，而不是维护一份容易过期的万能 YAML。它只改写 reference、secondary、DEM、frequency/polarization、product/scratch/log 路径；其他处理参数保持模板值。

```bash
/home/griffin/miniconda3/envs/insar/bin/python -m insar_pilot.cli.nisar run-rifg \
  --reference /data/nisar-project/subsets/reference_subset.h5 \
  --secondary /data/nisar-project/subsets/secondary_subset.h5 \
  --dem /data/dem/copernicus_ellipsoid.vrt \
  --template /data/templates/validated_rifg.yaml \
  --output /data/nisar-project/rifg-run-001 \
  --frequency A \
  --polarization HH \
  --python /home/griffin/miniconda3/envs/insar-nisar/bin/python
```

输出目录包含 `runconfig/`、`scratch/`、`products/RIFG_product.h5` 和 `logs/`。执行成功后只读取 HDF5 元数据，检查 productType、wrappedInterferogram、coherenceMagnitude、二维 shape 和 dtype，不加载完整栅格。

保留的 `run-rifg` 命令用于只生产 RIFG。需要继续解缠和地理编码时使用统一命令：

```bash
/home/griffin/miniconda3/envs/insar/bin/python -m insar_pilot.cli.nisar run-insar \
  --product-type GUNW \
  --reference /data/nisar-project/subsets/reference_subset.h5 \
  --secondary /data/nisar-project/subsets/secondary_subset.h5 \
  --dem /data/dem/copernicus_ellipsoid.vrt \
  --template /data/templates/validated_insar.yaml \
  --output /data/nisar-project/gunw-run-001 \
  --frequency A \
  --polarization HH \
  --geocode-bounds LEFT TOP RIGHT BOTTOM \
  --python /home/griffin/miniconda3/envs/insar-nisar/bin/python
```

`--product-type` 支持 `RIFG`、`RUNW` 和 `GUNW`。GUNW 建议显式提供与 AOI 对应、并与 runconfig 中输出 EPSG 一致的投影坐标边界，顺序为左、上、右、下。完成后可用 `validate-insar` 独立检查 RIFG/RUNW/GUNW 的 productType、相位、相干性、连通分量、shape 和 dtype。

## 7. 2026-09-04 真实验收

- 示例 AOI + 2026-06-26 至 2026-07-10 + descending path 13/frame 71 命中 2 景 PR RSLC，约 27.04 GiB 和 26.35 GiB。
- Earthdata/ASF 认证读取返回 HTTP 206，Range 可用，HDF5 signature 正确；未把账号或口令写入文件。
- openSEPPO 0.7.1 对本地两景完整 RSLC 子集化成功：38.07 秒，生成 2 个 AOI RSLC HDF5。
- ISCE3 0.25.17 CPU workflow 实际执行成功：23.10 秒；RIFG 为 A/HH、shape `569 × 674`、wrapped `complex64`、coherence `float32`。
- 同一对 openSEPPO AOI RSLC 子集在 ISCE3 0.25.17 上继续完成解缠和地理编码：完整 GUNW workflow 41.79 秒；中间 RUNW 为 `277 × 338`，最终 GUNW 为 `140 × 117`，unwrapped/coherence 均为 `float32`，GUNW 投影为 EPSG:32611。
- 直接以两条 Earthdata HTTPS granule URL 运行 openSEPPO（未启用完整缓存）成功：224.11 秒生成 44,774,547 与 44,671,660 字节的两景 AOI RSLC。与本地 golden 源生成的子集相比，每景 143 个对象、120 个数据集、零 schema 差异，119 个数据集逐元素完全相同；唯一数据差异是按代表性地形高度重新计算的 `boundingPolygon`。
- 远程子集继续运行 ISCE3：RIFG 18.48 秒，wrapped phase 对 golden 的圆周 RMSE 为 `2.10e-7 rad`；GUNW 25.12 秒，最终 `140 × 117`、EPSG:32611，unwrapped phase 对本地 golden 子集对照运行的 RMSE 为 `4.05e-7 rad`，坐标轴和 connected components 完全一致。
- openSEPPO 自动高程实测：未传 min/max 时，USGS 返回 AOI 五点最高地形约 938 m，加 500 m 后按 1438 m 裁剪；两景输出约 36.2 MB，比手动 0–3000 m 方案小约 19%，并成功生成 `536 × 577` RIFG。自动值依赖在线服务和当时响应，生产任务更推荐从项目 DEM 预先计算、固化并记录高度范围。
- 两个已有黄金 RIFG（AOI subset 与 phase2 full test）也通过同一 validator。

本次没有重复下载约 53 GiB 的完整文件，因为相同 granule 已存在于只读黄金数据目录；认证 Range 探测验证了实际下载权限，下载器单元/集成测试验证了任务路径、partial、原子改名和重试行为。
