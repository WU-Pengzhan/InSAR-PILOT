"""Native Linux and Windows browser hand-off without logging session credentials."""

from insar_pilot.web import launch


def test_linux_uses_native_browser(monkeypatch):
    monkeypatch.delenv("WSL_DISTRO_NAME", raising=False)
    calls = []
    monkeypatch.setattr(launch.webbrowser, "open", lambda url: calls.append(url) or True)
    assert launch.open_browser("http://127.0.0.1:8765/#token=fixture")
    assert len(calls) == 1


def test_wsl_uses_windows_browser_and_passes_credential_through_stdin(monkeypatch):
    monkeypatch.setenv("WSL_DISTRO_NAME", "Ubuntu")
    monkeypatch.setattr(launch.shutil, "which", lambda _name: "/mounted/windows/powershell.exe")
    calls = []
    monkeypatch.setattr(launch.subprocess, "run", lambda args, **kwargs: calls.append((args, kwargs)))
    url = "http://127.0.0.1:8765/#token=fixture"
    assert launch.open_browser(url)
    args, kwargs = calls[0]
    assert args[0] == "/mounted/windows/powershell.exe"
    assert not any("fixture" in arg for arg in args)
    assert kwargs["input"] == url + "\n"
    assert not kwargs.get("shell")


def test_browser_failure_is_reported(monkeypatch):
    monkeypatch.setenv("WSL_DISTRO_NAME", "Ubuntu")
    monkeypatch.setattr(launch.shutil, "which", lambda _name: None)
    monkeypatch.setattr(launch.webbrowser, "open", lambda _url: False)
    assert not launch.open_browser("http://127.0.0.1:8765/#token=fixture")


def test_explicit_wsl_browser_does_not_fall_back_to_default(monkeypatch):

    monkeypatch.setenv("WSL_DISTRO_NAME", "Ubuntu")
    monkeypatch.setattr(launch.shutil, "which", lambda _: "/windows/powershell.exe")
    calls = []
    monkeypatch.setattr(launch.subprocess, "run", lambda args, **kwargs: calls.append((args, kwargs)))
    assert launch.open_browser("http://127.0.0.1:8765/#token=fixture", "firefox")
    assert "firefox.exe" in calls[0][0][-1]
    assert "fixture" not in " ".join(calls[0][0])
    monkeypatch.setattr(launch.subprocess, "run", lambda *a, **kw: (_ for _ in ()).throw(OSError()))
    monkeypatch.setattr(launch.webbrowser, "open", lambda _: (_ for _ in ()).throw(AssertionError("wrong browser")))
    assert not launch.open_browser("http://127.0.0.1:8765/", "edge")


def test_explicit_linux_browser(monkeypatch):
    monkeypatch.delenv("WSL_DISTRO_NAME", raising=False)
    calls = []

    class Browser:
        def open(self, url):
            calls.append(url)
            return True

    monkeypatch.setattr(launch.webbrowser, "get", lambda name: Browser() if name == "firefox" else None)
    assert launch.open_browser("http://127.0.0.1:8765/", "firefox")
    assert calls == ["http://127.0.0.1:8765/"]


def test_occupied_port_is_not_silently_changed():
    import socket

    import pytest

    with socket.socket() as server:
        server.bind(("127.0.0.1", 0))
        server.listen()
        with pytest.raises(OSError):
            launch.available_port(server.getsockname()[1])
