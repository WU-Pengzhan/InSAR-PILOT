# 安装 1.5.0

InSAR-PILOT 在 Ubuntu 或 WSL2 Ubuntu 中运行，通过浏览器使用。应用支持 Python 3.10–3.12，不需要 Qt、WSLg 或图形显示服务。科学处理环境由用户单独管理。

## 从发行包安装

从 [1.5.0 发布页](https://github.com/WU-Pengzhan/InSAR-PILOT/releases/tag/v1.5.0) 下载 wheel，在下载目录执行：

```bash
python3 -m venv --copies ~/.local/share/insar-pilot/web-venv
~/.local/share/insar-pilot/web-venv/bin/python -m pip install ./insar_pilot-1.5.0-py3-none-any.whl
~/.local/share/insar-pilot/web-venv/bin/insar-pilot
```

如系统缺少 venv，先安装 Ubuntu 的 `python3-venv` 包。发行包包含 Web 界面，无需 Node。可用发布页的 `SHA256SUMS` 核对文件。
解压源码发行包后，也可在根目录运行 `bash install.sh`；可传入自定义虚拟环境路径。脚本只安装应用，不修改科学环境。

## 启动与关闭

激活安装环境后，`insar-pilot` 与 `insar-pilot-web` 等价：

```bash
insar-pilot --no-browser
insar-pilot --browser firefox
insar-pilot --status
insar-pilot --stop
```

启动后打开 `http://127.0.0.1:8765/`，WSL 用户可直接用 Windows 浏览器访问。
同一时刻仅一个窗口进入，其余自动等待。关闭浏览器不取消任务；`--stop` 在无活动任务时退出服务。
使用 `--port` 指定其他端口，被占用时不会静默换端口。
应用状态默认在 `~/.local/state/insar-pilot`；工程数据留在用户选择的目录。正式环境和状态不要放在 `/tmp`。

## 开发安装

```bash
python3 -m venv --copies .venv-web
.venv-web/bin/python -m pip install -e '.[dev]'
cd frontend
npm ci
npm run build
cd ..
.venv-web/bin/insar-pilot
```

前端构建使用 Node 22。旧的 `.[web]` 写法仍兼容，Web 依赖已成为默认依赖。
`environment.yml` 是可选的应用 Conda 环境示例，不再安装完整科学运行时。

## 科学环境与旧工程

顶部“运行环境”检测所选 Python 的组件并显示原因。Web 能启动与 ISCE2/ISCE3 可用性是独立状态，详见[运行时说明](architecture/runtime-support.md)。
旧 CLI 工程通过导入创建新的 Web 工程；不要让旧 CLI 与 Web 引擎在同一工程内交替写入，见[CLI 兼容边界](cli.md)。
