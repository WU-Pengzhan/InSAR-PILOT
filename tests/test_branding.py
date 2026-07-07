from importlib import resources
from pathlib import Path

import insar_pilot
import insar_pilot.app
import insar_pilot.launch as launch
from insar_pilot.app.settings import AppSettings
from insar_pilot.domain.project import APP_METADATA_DIR, PROJECT_ROOT_FILE_NAME
from insar_pilot.i18n import Translator

REPO_ROOT = Path(__file__).resolve().parents[1]


def test_public_package_and_application_branding():
    assert insar_pilot.__version__ == "1.1.0"
    assert insar_pilot.app.main is launch.main
    assert launch.APP_NAME == "InSAR-PILOT"
    assert AppSettings.APPLICATION == "InSAR-PILOT"
    assert Translator("en").tr("app.title") == "InSAR-PILOT"


def test_project_workspace_branding_constants():
    assert PROJECT_ROOT_FILE_NAME == "project.pilot"
    assert APP_METADATA_DIR == ".insar_pilot"


def test_pyproject_exposes_only_insar_pilot_cli():
    text = (REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert 'name = "insar-pilot"' in text
    assert 'insar-pilot = "insar_pilot.app:main"' in text
    assert '"insar_pilot.ui.assets" = ["*.png"]' in text
    assert "sentinel" + "-workbench" not in text
    assert "isce2" + "-gui" not in text


def test_branding_assets_are_packaged_and_documented():
    package_files = resources.files("insar_pilot.ui.assets")
    assert package_files.joinpath("logo.png").is_file()
    assert package_files.joinpath("logo-mark.png").is_file()

    for relative in [
        "docs/assets/branding/logo.png",
        "docs/assets/branding/logo-mark.png",
        "docs/assets/branding/github-avatar.png",
        "docs/assets/branding/github-social-preview.png",
    ]:
        assert (REPO_ROOT / relative).is_file()

    expected_links = {
        "README.md": "docs/assets/branding/logo.png",
        "README_EN.md": "docs/assets/branding/logo.png",
        "docs/user-guide.md": "assets/branding/logo.png",
        "docs/en/user-guide.md": "assets/branding/logo.png",
    }
    for relative, link in expected_links.items():
        assert link in (REPO_ROOT / relative).read_text(encoding="utf-8")


def test_repository_has_no_old_public_brand_strings():
    ignored_dirs = {".git", ".pytest_cache", ".ruff_cache", "__pycache__", "dist"}
    old_terms = [
        "Sentinel-1 Processing " + "Workbench",
        "sentinel" + "-workbench",
        "isce2" + "-gui",
        "isce2" + "_gui",
        "isce" + "-master",
        "SENTINEL" + "_WORKBENCH",
        "sentinel1" + "_project",
        ".sentinel1" + "_workbench",
        "ISCE2" + "_GUI",
    ]
    offenders: list[str] = []
    for path in REPO_ROOT.rglob("*"):
        if any(part in ignored_dirs for part in path.parts):
            continue
        if path.name == "test_branding.py":
            continue
        if not path.is_file():
            continue
        if path.suffix in {".png", ".pyc"}:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for term in old_terms:
            if term in text:
                offenders.append(f"{path.relative_to(REPO_ROOT)}: {term}")
    assert offenders == []
