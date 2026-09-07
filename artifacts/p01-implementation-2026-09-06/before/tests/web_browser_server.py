"""Isolated local server for browser tests; never starts numerical workers."""

import os
from pathlib import Path
from tempfile import TemporaryDirectory

import uvicorn

from insar_pilot.infrastructure.engine_store import EngineStore
from insar_pilot.web.api import create_app

if __name__ == "__main__":
    with TemporaryDirectory(prefix="pilot-picker-e2e-") as directory:
        root = Path(directory)
        app = create_app(root, "local-picker-test-session", testing=True)
        fixtures = root / "library" / "Picker fixtures"
        fixtures.mkdir()
        (fixtures / "目录 空格").mkdir()
        (fixtures / "scene.SAFE").mkdir()
        (fixtures / ".hidden").mkdir()
        long_folder = fixtures / ("Long folder name " + "for layout verification " * 5)
        long_folder.mkdir()
        for index in range(40):
            (long_folder / f"Directory {index:02d}").mkdir()
        (fixtures / "scene.h5").write_bytes(b"Browser selection fixture, not a scientific product.")
        app.state.registry.register(EngineStore.create(fixtures / "Existing Project", "Picker existing"))
        uvicorn.run(app, host="127.0.0.1", port=int(os.environ.get("PILOT_E2E_PORT", "8767")), access_log=False)
