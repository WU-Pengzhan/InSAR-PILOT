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
