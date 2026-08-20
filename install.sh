#!/usr/bin/env bash
set -Eeuo pipefail

environment_name="${1:-insar}"
project_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"

if ! command -v conda >/dev/null 2>&1; then
    echo "Error: conda was not found on PATH." >&2
    echo "Install and initialize Miniconda, Anaconda, or Miniforge, then reopen the shell." >&2
    exit 1
fi

if [[ ! "$environment_name" =~ ^[A-Za-z0-9._-]+$ ]]; then
    echo "Error: invalid Conda environment name: $environment_name" >&2
    exit 1
fi

echo "Installing InSAR-PILOT into Conda environment '$environment_name'..."
if conda run -n "$environment_name" python -c "import sys" >/dev/null 2>&1; then
    conda env update -n "$environment_name" -f "$project_dir/environment.yml"
else
    conda env create -n "$environment_name" -f "$project_dir/environment.yml"
fi

conda run --no-capture-output -n "$environment_name" \
    python -m pip install --upgrade --no-deps "$project_dir"
conda run --no-capture-output -n "$environment_name" \
    python "$project_dir/scripts/verify_install.py"

if grep -qi microsoft /proc/version 2>/dev/null \
    && [[ -z "${DISPLAY:-}" && -z "${WAYLAND_DISPLAY:-}" ]]; then
    echo "Warning: no WSLg/X display was detected. CLI use is available, but the GUI needs WSLg or an X server."
fi

echo
echo "Installation complete. Start InSAR-PILOT with:"
echo "  conda activate $environment_name"
echo "  insar-pilot"
