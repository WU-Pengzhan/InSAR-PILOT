"""Regression tests for scaled quicklook decoding and controller wiring."""

from pathlib import Path
from types import SimpleNamespace

import pytest
from PySide6.QtCore import QPoint, QPointF, Qt
from PySide6.QtGui import QImage, QWheelEvent
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
def test_preview_panel_retains_full_resolution_source_pixels(tmp_path: Path, suffix: str):
    _qt_app()
    image_path = tmp_path / f"large{suffix}"
    _write_image(image_path, 3200, 1600)
    panel = PreviewPanel()

    info = panel.load_image(image_path)

    assert info.original_width == 3200
    assert info.original_height == 1600
    assert info.display_width / info.display_height == pytest.approx(2.0, rel=0.01)
    assert panel.image_view.has_image
    assert panel.image_view.image_size.width() == 3200
    assert panel.image_view.image_size.height() == 1600


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

    assert panel.image_view.has_image is False
    assert panel._metadata == "technical details"


def test_preview_panel_ctrl_wheel_zooms_and_plain_wheel_scrolls(tmp_path: Path):
    app = _qt_app()
    image_path = tmp_path / "square.png"
    _write_image(image_path, 1200, 1200)
    panel = PreviewPanel()
    panel.resize(760, 620)
    panel.show()
    app.processEvents()
    panel.load_image(image_path)
    app.processEvents()
    initial_zoom = panel.zoom_factor

    ctrl_zoom = QWheelEvent(
        QPointF(240, 180),
        QPointF(240, 180),
        QPoint(),
        QPoint(0, 120),
        Qt.MouseButton.NoButton,
        Qt.KeyboardModifier.ControlModifier,
        Qt.ScrollPhase.NoScrollPhase,
        False,
    )
    QApplication.sendEvent(panel.scroll_area.viewport(), ctrl_zoom)
    app.processEvents()

    assert panel.zoom_factor > initial_zoom
    assert panel.image_view.verticalScrollBar().maximum() > 0

    scroll = QWheelEvent(
        QPointF(240, 180),
        QPointF(240, 180),
        QPoint(),
        QPoint(0, -120),
        Qt.MouseButton.NoButton,
        Qt.KeyboardModifier.NoModifier,
        Qt.ScrollPhase.NoScrollPhase,
        False,
    )
    QApplication.sendEvent(panel.scroll_area.viewport(), scroll)
    app.processEvents()

    assert panel.image_view.verticalScrollBar().value() > 0
    panel.close()


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

        def set_color_range(self, minimum: float, maximum: float) -> None:
            self.color_range = (minimum, maximum)

    class _PageSpy:
        def __init__(self, preview_panel) -> None:
            self.preview_panel = preview_panel
            self.image_dimensions = ""
            self.details = ""
            self.stale = True

        def set_image_dimensions(self, text: str) -> None:
            self.image_dimensions = text

        def set_details(self, text: str) -> None:
            self.details = text

        def set_stale(self, stale: bool) -> None:
            self.stale = stale

    parent = QWidget()
    panel = _PanelSpy()
    parent.results_page = _PageSpy(panel)
    controller = ResultsController(
        parent,  # type: ignore[arg-type]
        result_catalog_service=SimpleNamespace(),  # type: ignore[arg-type]
        visualization_service=SimpleNamespace(),  # type: ignore[arg-type]
    )

    controller._display_preview_image(str(image_path), "Quicklook ready")

    assert calls == [image_path]
    assert "Image size: 2000 × 1000" in parent.results_page.details
    assert parent.results_page.stale is False
