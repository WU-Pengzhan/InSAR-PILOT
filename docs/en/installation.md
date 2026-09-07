# Install 1.5.0

Run on Ubuntu or WSL2 Ubuntu with Python 3.10–3.12. Qt, WSLg and a display server are unnecessary. Scientific runtimes are managed separately.
Download the wheel from [Releases](https://github.com/WU-Pengzhan/InSAR-PILOT/releases/tag/v1.5.0), then run in the download directory:

```bash
python3 -m venv --copies ~/.local/share/insar-pilot/web-venv
~/.local/share/insar-pilot/web-venv/bin/python -m pip install ./insar_pilot-1.5.0-py3-none-any.whl
~/.local/share/insar-pilot/web-venv/bin/insar-pilot
```

Install Ubuntu's `python3-venv` if needed. Release packages include the interface; Node is for frontend development. Check files against `SHA256SUMS`. Alternatively unpack the source distribution and run `bash install.sh`; its optional argument is a virtual-environment path.

## Start and stop

After activating the installation environment:

```bash
insar-pilot --no-browser
insar-pilot --browser firefox
insar-pilot --status
insar-pilot --stop
```

`insar-pilot-web` is an equivalent command. Open `http://127.0.0.1:8765/`, including from Windows when using WSL. One window enters; other windows wait. Closing a browser leaves tasks running; explicit shutdown requires idle tasks. Use `--port` for another port.
Application state defaults to `~/.local/state/insar-pilot`, separate from project data. Use persistent locations.

## Development and scientific environments

Install editable with `python -m pip install -e '.[dev]'`. In `frontend/`, run `npm ci` and `npm run build` using Node 22. The `web` extra remains compatible; Web dependencies are now installed by default. `environment.yml` is an application-only Conda example.
Runtime status checks your scientific Python; it does not install ISCE2/ISCE3. See the [runtime contract](../architecture/runtime-support.md). Import legacy CLI projects into new Web projects rather than alternating execution stores in place.
