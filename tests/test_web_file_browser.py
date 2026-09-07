"""Host-side selections work without browser upload or a desktop dialog service."""

from pathlib import Path
from subprocess import CompletedProcess

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("httpx")
from fastapi.testclient import TestClient

from insar_pilot.web.api import create_app
from insar_pilot.web.file_browser import host_path


@pytest.fixture
def client(tmp_path):
    with TestClient(create_app(tmp_path / "state", "picker-session", testing=True)) as client:
        client.headers["Authorization"] = "Bearer picker-session"
        yield client


def resolve(client, path):
    response = client.post("/api/v1/filesystem/resolve", json={"path": str(path)})
    assert response.status_code == 200, response.text
    return response.json()


def test_picker_requires_local_session_and_origin(client, tmp_path):
    assert client.get("/api/v1/filesystem/locations", headers={"Authorization": "wrong"}).status_code == 401
    assert (
        client.post(
            "/api/v1/filesystem/resolve", json={"path": str(tmp_path)}, headers={"Origin": "https://example.com"}
        ).status_code
        == 403
    )
    assert client.get("/api/v1/filesystem/directories/forged").status_code == 422


def test_linux_navigation_unicode_hidden_search_pagination_and_metadata_only(client, tmp_path, monkeypatch):
    monkeypatch.delenv("WSL_DISTRO_NAME", raising=False)
    root = tmp_path / "输入 data"
    root.mkdir()
    (root / "A.SAFE").mkdir()
    (root / "B.h5").write_text("never transmit this content")
    (root / "C.h5").write_bytes(b"data")
    (root / ".hidden").mkdir()
    locations = client.get("/api/v1/filesystem/locations").json()
    assert locations["environment"] == "linux"
    assert locations["locations"][0]["path"] == str(Path.home())
    resolved = resolve(client, root)
    url = f"/api/v1/filesystem/directories/{resolved['directory_id']}"
    first = client.get(url, params={"limit": 2}).json()
    assert [e["name"] for e in first["entries"]] == ["A.SAFE", "B.h5"]
    assert first["next_offset"] == 2
    assert "never transmit" not in str(first)
    second = client.get(url, params={"limit": 2, "offset": 2}).json()
    assert [e["name"] for e in second["entries"]] == ["C.h5"]
    assert second["next_offset"] is None
    assert client.get(url, params={"search": "b.H5"}).json()["entries"][0]["name"] == "B.h5"
    folders = client.get(url, params={"directories_only": True, "hidden": True}).json()
    assert {e["name"] for e in folders["entries"]} == {".hidden", "A.SAFE"}
    assert first["breadcrumbs"][-1]["path"] == str(root)
    parent = client.get(f"/api/v1/filesystem/directories/{first['parent_id']}").json()
    assert parent["directory"]["path"] == str(tmp_path)
    assert client.get(url, params={"limit": 501}).status_code == 422
    assert client.get(url, params={"offset": -1}).status_code == 422


def test_selection_is_read_only_missing_files_and_permission_errors(client, tmp_path, monkeypatch):
    root = tmp_path / "empty"
    root.mkdir()
    directory = resolve(client, root)
    url = f"/api/v1/filesystem/directories/{directory['directory_id']}"
    assert client.get(url).json()["entries"] == []
    assert list(root.iterdir()) == []
    assert client.post("/api/v1/filesystem/resolve", json={"path": str(root / "new")}).status_code == 422
    assert not (root / "new").exists()

    def denied(_path):
        raise PermissionError("Permission denied")

    with monkeypatch.context() as patch:
        patch.setattr("insar_pilot.web.file_browser.os.scandir", denied)
        response = client.get(url)
        assert response.status_code == 422
        assert "Permission denied" in response.json()["detail"]
    root.rmdir()
    assert client.get(url).status_code == 422


def test_python_symlink_location_is_preserved(client, tmp_path):
    binary = tmp_path / "system-python"
    binary.write_bytes(b"fixture")
    env = tmp_path / "venv" / "bin"
    env.mkdir(parents=True)
    python = env / "python"
    python.symlink_to(binary)
    result = resolve(client, python)
    assert result["entry"]["path"] == str(python)
    listing = client.get(f"/api/v1/filesystem/directories/{result['directory_id']}").json()
    assert listing["entries"][0]["path"] == str(python)


def test_wsl_unc_paths_reach_same_project_and_other_distros_rejected(client, tmp_path, monkeypatch):
    monkeypatch.setenv("WSL_DISTRO_NAME", "Ubuntu")
    root = tmp_path / "工程"
    root.mkdir()
    unc = "\\\\wsl.localhost\\Ubuntu" + str(root).replace("/", "\\")
    assert resolve(client, unc)["entry"]["path"] == str(root)
    assert client.get("/api/v1/filesystem/locations").json()["environment"] == "wsl"
    project = client.post("/api/v1/projects", json={"name": "WSL", "path": unc}).json()
    opened = client.post("/api/v1/projects/open", json={"path": unc + "\\WSL.pilot"})
    assert opened.status_code == 200
    assert opened.json()["project_id"] == project["project_id"]
    bad = unc.replace("Ubuntu", "Debian")
    assert client.post("/api/v1/filesystem/resolve", json={"path": bad}).status_code == 422
    monkeypatch.delenv("WSL_DISTRO_NAME")
    assert client.post("/api/v1/filesystem/resolve", json={"path": unc}).status_code == 422


def test_windows_drive_mapping_uses_wsl_mount_configuration_without_shell(monkeypatch):
    monkeypatch.setenv("WSL_DISTRO_NAME", "Ubuntu")
    calls = []

    def convert(args, **kwargs):
        calls.append((args, kwargs))
        return CompletedProcess(args, 0, "/windows/c/SAR data/样本.h5\n", "")

    monkeypatch.setattr("insar_pilot.web.file_browser.subprocess.run", convert)
    windows = "C:\\SAR data\\样本.h5"
    assert str(host_path(windows)) == "/windows/c/SAR data/样本.h5"
    assert calls[0][0] == ["wslpath", "-u", windows]
    assert not calls[0][1].get("shell")
    assert str(host_path("\\\\wsl$\\Ubuntu\\home\\user")) == "/home/user"
    for invalid in ("C:relative", "\\\\server\\share", "relative/path", "\x00"):
        with pytest.raises(ValueError):
            host_path(invalid)
    monkeypatch.delenv("WSL_DISTRO_NAME")
    with pytest.raises(ValueError, match="require WSL"):
        host_path(windows)
