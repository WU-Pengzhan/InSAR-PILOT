#!/usr/bin/env bash
set -Eeuo pipefail
project_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
web_env="${1:-$HOME/.local/share/insar-pilot/web-venv}"
python_bin="${PYTHON:-python3}"
if [[ ! -f "$project_dir/src/insar_pilot/web/static/index.html" ]]; then
    echo "Missing built Web interface. Build frontend first: cd frontend && npm ci && npm run build" >&2
    exit 1
fi
if [[ ! -x "$web_env/bin/python" ]]; then
    "$python_bin" -m venv --copies "$web_env"
fi
"$web_env/bin/python" -m pip install --upgrade "$project_dir"
"$web_env/bin/python" "$project_dir/scripts/verify_install.py"
echo "Installed. Start: $web_env/bin/insar-pilot"
echo "Scientific environments are configured separately in the workbench."
