# 故障排查

本页汇总 InSAR-PILOT 在 WSL2/WSLg 与 Ubuntu Desktop 上的常见运行问题。

## 1. GUI 显示后端无法启动

症状：

- 应用在主窗口出现前就退出
- Qt 报告 `xcb` 或 `wayland` 无法初始化
- 下拉框或弹出窗口行为异常

启动器会在创建窗口前探测显示后端：

- WSL2/WSLg 优先 `xcb`，失败后回退 `wayland`
- 原生 Ubuntu Wayland 优先 `wayland`，失败后回退 `xcb`
- 用户显式设置的 `QT_QPA_PLATFORM` 始终优先

手动指定：

```bash
QT_QPA_PLATFORM=xcb insar-pilot
```

```bash
QT_QPA_PLATFORM=wayland insar-pilot
```

WSL2 下先确认图形显示可用：

```bash
echo "$DISPLAY"
echo "$WAYLAND_DISPLAY"
```

若 Qt 报缺少 xcb 运行库：

```bash
sudo apt install -y libxcb-cursor0 libxcb-xinerama0 libxkbcommon-x11-0
```

查看启动器诊断信息：

```bash
INSAR_PILOT_DEBUG_LAUNCH=1 insar-pilot
```

## 2. 地图吞掉点击或窗口像被冻结

症状：

- 启动页工作正常
- 打开项目后，地图可以拖动，但按钮/表单没有响应
- 常见于 WSLg、多显示器布局、窗口最大化或混合 DPI 场景

可能原因：

- QtWebEngine/Chromium 创建的原生子窗口携带了过期的事件几何信息。

绕过方法：

```bash
INSAR_PILOT_MAP_BACKEND=native insar-pilot
```

这会禁用 Leaflet 底图，改用原生几何预览，保证 GUI 其余部分可以正常点击。

## 3. 环境校验失败

先在 Setup 页面运行环境校验。

检查：

- 应用是否从预期的 conda 环境启动，例如 `conda activate insar`
- ISCE2、GDAL、`snaphu`、`stackSentinel.py`、`sentineleof`、`aria2c` 在当前运行时中可被发现
- 项目文件夹与处理工作目录可写
- SLC、EOF 轨道文件、DEM 路径存在

应用从**启动它的进程**探测运行时。推荐：

```bash
conda activate insar
insar-pilot
```

## 4. ASF 检索或下载失败

检查：

- Earthdata 账户有效，且已在 Data 页面测试通过
- 起止日期已设置
- AOI 是有效的 bbox 或受支持的 KML/WKT 来源
- 当前环境中已安装 `aria2c`
- 项目 `data/` 目录可写

SLC 下载依赖 aria2c 后端的分片续传能力。EOF 下载使用运行时环境中安装的轨道下载工具。

## 5. DEM 准备失败

检查清单：

- DEM 路径存在且可读
- 直接导入时，GeoTIFF DEM 必须是 WGS84 地理坐标网格
- 高程基准选择正确
- 处理工作目录可写
- 查看项目文件夹下 `logs/` 中的日志

若出现 DEM 覆盖范围警告，请换用在目标 bbox 与条带覆盖范围外留有空间余量的 DEM。

## 6. run_files 执行失败

在 Run 页面查看：

- 失败的 step 名称
- subcommand 序号
- 命令文本
- stdout/stderr 日志路径
- exit code

常见修复：

- 在 Setup 中重新运行 `Validate` 和 `Preflight`
- 检查 `processing/work/` 的写权限
- 确认 SLC SAFE/ZIP、EOF、DEM 输入仍然存在
- 修复失败步骤后使用 `Run Selected Step` 续跑

## 7. 日志与项目状态的位置

项目文件夹内：

```text
project_root/
  project.pilot
  logs/
  processing/work/
  .insar_pilot/cache/
```

重要日志包括：

- 工作流生成日志
- run 文件批次与命令日志
- DEM 导入/准备日志
- 可视化日志

## 8. QtWebEngine 或 DBus 的终端告警

在 WSL/conda 桌面会话中可能出现诸如缺少 DBus socket 之类的提示。只要 GUI 能正常启动并工作，这些通常是无害的 Chromium/桌面集成告警。
