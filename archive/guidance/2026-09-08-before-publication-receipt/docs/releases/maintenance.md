# 发行维护

## 版本与检查

版本以 pyproject.toml、insar_pilot.__version__、frontend/package.json 和 package-lock.json 为准；API 从 __version__ 读取。更新 CITATION 与 CHANGELOG，刷新 uv.lock。

```bash
uv sync --extra dev --locked
uv run ruff check src tests scripts
uv run mypy src/insar_pilot/domain src/insar_pilot/services src/insar_pilot/download src/insar_pilot/cli
uv run pytest -q
cd frontend
npm ci
npm test
npm run build
cd ..
uv run mkdocs build --strict
uv run python -m build
uv run python scripts/check_release.py
```

运行与修改相关的浏览器验收。打包前确保 dist 只含目标版本，清理旧 build 中的残留模块，防止旧 Qt 被 setuptools 带入 wheel。
从 wheel 建立独立环境验证默认入口、静态界面、启动/状态/退出；只用隔离状态目录与空闲测试端口。
`check_release.py` 检查资源、Web 默认入口与无 Qt 依赖；源码包同时保留前端源码与锁文件。

## 发布

确认远端 main 与本地历史可快进，提交已验证内容后推送 main 和版本标签。禁止重写已有标签或强推。
Release workflow 在标签 push 后构建并上传 wheel、sdist 与 SHA256SUMS。人工发布时使用同一份版本说明与校验过的产物，避免并发覆盖。
README 作为产品介绍，安装细节归用户指南，执行证据归 handoff，产品范围只由 architecture 定义。
清理清单为 `archive/cleanup-v1.5.0.json`；历史指导在 archive/guidance 中附 SHA-256 原样保存。浏览器测试 profile 不纳入发行包。
