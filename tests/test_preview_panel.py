"""Regression tests for scaled quicklook decoding and controller wiring."""

from pathlib import Path
from types import SimpleNamespace

import pytest
from PySide6.QtGui import QImage
from PySide6.QtWidgets import QApplication, QWidget

from insar_pilot.ui.controllers.results_controller import ResultsController
from insar_pilot.ui.widgets.preview_panel import PreviewImageInfo, PreviewPanel


def _qt_app() -> QApplication:
    app = QApplication.instance()
    return app if app is not None else QApplication([])


def _write_image(path: Path, width: int, height: int) -> None:
    image = QImage(width, height, QImage.Format.Format_RGB32)
    image.fill(0xFF336699)
    assert image.save(str(path))


@pytest.mark.parametrize("suffix", [".png", ".bmp"])
def test_preview_panel_decodes_large_file_at_bounded_size(tmp_path: Path, suffix: str):
    _qt_app()
    image_path = tmp_path / f"large{suffix}"
    _write_image(image_path, 3200, 1600)
    panel = PreviewPanel()

    info = panel.load_image(image_path)

    assert info.original_width == 3200
    assert info.original_height == 1600
    assert info.display_width <= PreviewPanel.MAX_PREVIEW_SIZE.width()
    assert info.display_height <= PreviewPanel.MAX_PREVIEW_SIZE.height()
    assert info.display_width / info.display_height == pytest.approx(2.0, rel=0.01)
    assert panel.image_label.pixmap() is not None
    assert panel.image_label.pixmap().size().width() == info.display_width


def test_preview_panel_rejects_missing_and_corrupt_files(tmp_path: Path):
    _qt_app()
    panel = PreviewPanel()

    with pytest.raises(FileNotFoundError):
        panel.load_image(tmp_path / "missing.png")

    corrupt = tmp_path / "corrupt.png"
    corrupt.write_bytes(b"not an image")
    with pytest.raises(ValueError):
        panel.load_image(corrupt)


def test_preview_panel_clear_restores_empty_state():
    _qt_app()
    panel = PreviewPanel()

    panel.clear_image("Rendering preview")
    panel.set_metadata("technical details")

    assert panel.image_label.text() == "Rendering preview"
    assert panel.meta_text.toPlainText() == "technical details"
    pixmap = panel.image_label.pixmap()
    assert pixmap is None or pixmap.isNull()


def test_results_controller_loads_preview_through_panel(tmp_path: Path):
    _qt_app()
    image_path = tmp_path / "preview.png"
    image_path.touch()
    calls: list[Path] = []

    class _PanelSpy:
        def __init__(self) -> None:
            self.metadata = ""

        def load_image(self, path: str | Path) -> PreviewImageInfo:
            resolved = Path(path)
            calls.append(resolved)
            return PreviewImageInfo(resolved, 2000, 1000, 1600, 800)

        def clear_image(self, message: str | None = None) -> None:
            raise AssertionError(f"unexpected clear: {message}")

        def set_metadata(self, text: str) -> None:
            self.metadata = text

    class _CardSpy:
        def set_value(self, value: str) -> None:
            self.value = value

        def set_body(self, body: str) -> None:
            self.body = body

    parent = QWidget()
    panel = _PanelSpy()
    parent.results_page = SimpleNamespace(preview_panel=panel, preview_card=_CardSpy())
    controller = ResultsController(
        parent,  # type: ignore[arg-type]
        output_discovery_service=SimpleNamespace(),  # type: ignore[arg-type]
        visualization_service=SimpleNamespace(),  # type: ignore[arg-type]
    )

    controller._display_preview_image(str(image_path), "Quicklook ready")

    assert calls == [image_path]
    assert "Image size: 2000 x 1000" in panel.metadata
    assert "Displayed size: 1600 x 800" in panel.metadata
