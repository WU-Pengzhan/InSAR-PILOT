from __future__ import annotations

import insar_pilot.launch as launch


def test_workbench_development_switch_is_opt_in(monkeypatch):
    monkeypatch.delenv(launch.WORKBENCH_ENV_VAR, raising=False)
    assert launch.selected_ui_mode() == "legacy"

    monkeypatch.setenv(launch.WORKBENCH_ENV_VAR, "1")
    assert launch.selected_ui_mode() == "workbench"


def test_workbench_development_switch_rejects_unrecognized_values(monkeypatch):
    monkeypatch.setenv(launch.WORKBENCH_ENV_VAR, "preview")

    assert launch.selected_ui_mode() == "legacy"

