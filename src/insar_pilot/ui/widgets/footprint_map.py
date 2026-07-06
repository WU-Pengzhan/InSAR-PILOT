"""Search footprint map preview with optional Leaflet basemap."""

from __future__ import annotations

import html
from importlib import resources
import json
import os
import subprocess
import sys
from typing import Any

from PySide6.QtCore import QEvent, QRect, QTimer, Qt
from PySide6.QtWidgets import QStackedWidget, QVBoxLayout, QWidget

from insar_pilot.download.geometry import (
    aoi_geojson_from_inputs,
    bounds_from_geojson,
    polygons_from_geojson,
)
from insar_pilot.download.models import SceneRecord, SearchCriteria
from insar_pilot.ui.widgets.geometry_verify_panel import GeometryVerifyPanel, VerifyPlotData


def _qtwebengine_is_importable() -> tuple[bool, str]:
    """Return whether QtWebEngine can be imported without crashing the app."""

    try:
        probe = subprocess.run(
            [
                sys.executable,
                "-c",
                "from PySide6.QtWebEngineWidgets import QWebEngineView; "
                "from PySide6.QtWebEngineCore import QWebEnginePage",
            ],
            capture_output=True,
            text=True,
            timeout=3,
            check=False,
        )
    except Exception as exc:
        return False, str(exc)
    if probe.returncode == 0:
        return True, ""
    detail = (probe.stderr or probe.stdout).strip()
    if not detail:
        detail = f"QtWebEngine import exited with status {probe.returncode}."
    return False, detail


_WEBENGINE_AVAILABLE: bool | None = None
_WEBENGINE_REASON = ""
QWebEngineView = None


def _read_text_asset(name: str) -> str:
    """Read a bundled text asset used by the embedded map."""

    return resources.files("insar_pilot.ui.widgets.assets").joinpath(name).read_text(encoding="utf-8")


class FootprintMapWidget(QWidget):
    """Preview AOI and Sentinel-1 scene footprints."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._criteria: SearchCriteria | None = None
        self._scenes: list[SceneRecord] = []
        self._highlight_scene_id = ""
        self._selected_scene_ids: set[str] = set()
        self._dem_bbox_snwe: tuple[float, float, float, float] | None = None
        self._tianditu_enabled = False
        self._tianditu_proxy_url = ""
        self._preferred_basemap_name = "External Imagery"
        self._web_ready = False
        self._pending_render = False
        self._pending_fit_bounds = True
        self._sync_pending = False
        self.fallback_reason = ""

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        self.stack = QStackedWidget()
        self.stack.installEventFilter(self)
        layout.addWidget(self.stack)

        self.web_view = None
        self.geometry_panel = GeometryVerifyPanel()
        self.stack.addWidget(self.geometry_panel)
        self.stack.setCurrentWidget(self.geometry_panel)

    def set_data(
        self,
        criteria: SearchCriteria | None,
        scenes: list[SceneRecord],
        *,
        highlighted_scene_id: str = "",
        selected_scene_ids: set[str] | None = None,
    ) -> None:
        """Render AOI and scene footprints."""

        self._criteria = criteria
        self._scenes = list(scenes)
        self._highlight_scene_id = highlighted_scene_id
        self._selected_scene_ids = set(selected_scene_ids or set())
        self._render(fit_bounds=True)

    def set_highlight(self, scene_id: str, selected_scene_ids: set[str] | None = None) -> None:
        """Highlight one scene footprint after table selection changes."""

        self._highlight_scene_id = scene_id
        if selected_scene_ids is not None:
            self._selected_scene_ids = set(selected_scene_ids)
        if self.web_view is not None and self._web_ready:
            self._run_js(
                "window.updateHighlight && "
                f"window.updateHighlight({json.dumps(scene_id)}, {json.dumps(sorted(self._selected_scene_ids))});"
            )
            return
        self._render(fit_bounds=False)

    def clear(self) -> None:
        """Clear all rendered footprints."""

        self._criteria = None
        self._scenes = []
        self._highlight_scene_id = ""
        self._selected_scene_ids = set()
        self._dem_bbox_snwe = None
        self._web_ready = False
        self._render(fit_bounds=True)

    def set_dem_bbox(self, bbox_snwe: tuple[float, float, float, float] | None) -> None:
        """Render or clear a planned DEM coverage rectangle."""

        self._dem_bbox_snwe = bbox_snwe
        if self.web_view is not None and self._web_ready:
            self._run_js(
                "window.updateDem && "
                f"window.updateDem({json.dumps(self._dem_feature())});"
            )
            return
        self._render(fit_bounds=False)

    def set_tianditu_enabled(self, enabled: bool) -> None:
        """Update whether Tianditu should be offered as the default basemap."""

        self._tianditu_enabled = bool(enabled)
        self._web_ready = False
        self._render(fit_bounds=False)

    def set_tianditu_proxy_url(self, base_url: str) -> None:
        """Update the localhost base URL used for proxied Tianditu tiles."""

        self._tianditu_proxy_url = base_url.rstrip("/")
        self._web_ready = False
        self._render(fit_bounds=False)

    def set_preferred_basemap(self, name: str) -> None:
        """Set the preferred startup basemap for subsequent renders."""

        self._preferred_basemap_name = name or "External Imagery"
        self._web_ready = False
        self._render(fit_bounds=False)

    def set_tianditu_basemap_state(self, *, enabled: bool, preferred_basemap: str) -> None:
        """Update Tianditu availability and preferred basemap in one render."""

        self._tianditu_enabled = bool(enabled)
        self._preferred_basemap_name = preferred_basemap or "External Imagery"
        self._web_ready = False
        self._render(fit_bounds=False)

    def _render(self, *, fit_bounds: bool) -> None:
        if not self.isVisible():
            self._pending_render = True
            self._pending_fit_bounds = self._pending_fit_bounds or fit_bounds
            return

        aoi_geometry = self._aoi_geometry()
        if self._ensure_web_view():
            try:
                self.stack.setCurrentWidget(self.web_view)
                self._schedule_web_view_sync()
                self.web_view.setHtml(self._leaflet_html(aoi_geometry, self._scenes, fit_bounds=fit_bounds))
                self._web_ready = True
                self._pending_render = False
                self._pending_fit_bounds = False
                return
            except Exception as exc:
                self.fallback_reason = f"Embedded map failed; using geometry preview. {exc}"
        else:
            self.fallback_reason = self.fallback_reason or "QtWebEngine is not available; using geometry preview."
        self.stack.setCurrentWidget(self.geometry_panel)
        self._render_geometry_fallback(aoi_geometry)
        self._pending_render = False
        self._pending_fit_bounds = False

    def _ensure_web_view(self) -> bool:
        global QWebEngineView, _WEBENGINE_AVAILABLE, _WEBENGINE_REASON
        backend = os.environ.get("INSAR_PILOT_MAP_BACKEND", "webengine").strip().lower()
        if backend in {"native", "fallback", "geometry", "off", "disabled"}:
            self.fallback_reason = "Embedded map disabled by INSAR_PILOT_MAP_BACKEND; using geometry preview."
            return False
        if _WEBENGINE_AVAILABLE is None:
            _WEBENGINE_AVAILABLE, _WEBENGINE_REASON = _qtwebengine_is_importable()
            if _WEBENGINE_AVAILABLE:
                try:
                    from PySide6.QtWebEngineWidgets import QWebEngineView as LoadedWebEngineView

                    QWebEngineView = LoadedWebEngineView
                except Exception as exc:
                    _WEBENGINE_AVAILABLE = False
                    _WEBENGINE_REASON = str(exc)
        if QWebEngineView is None:
            self.fallback_reason = (
                f"QtWebEngine is not available; using geometry preview. {_WEBENGINE_REASON}".strip()
            )
            return False
        if self.web_view is None:
            self.web_view = QWebEngineView()
            self.web_view.setObjectName("footprintWebView")
            self.web_view.setFocusPolicy(Qt.FocusPolicy.ClickFocus)
            self.web_view.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent, True)
            self.web_view.installEventFilter(self)
            self.stack.insertWidget(0, self.web_view)
            self._schedule_web_view_sync()
        return self.web_view is not None

    def eventFilter(self, obj, event) -> bool:  # noqa: N802 - Qt override
        if (obj is self.stack or obj is self.web_view) and event.type() in {
            QEvent.Type.Show,
            QEvent.Type.Resize,
            QEvent.Type.Move,
            QEvent.Type.LayoutRequest,
        }:
            self._schedule_web_view_sync()
        return super().eventFilter(obj, event)

    def resizeEvent(self, event) -> None:  # noqa: N802 - Qt override
        super().resizeEvent(event)
        self._schedule_web_view_sync()

    def showEvent(self, event) -> None:  # noqa: N802 - Qt override
        super().showEvent(event)
        self._schedule_web_view_sync()
        if self._pending_render:
            fit_bounds = self._pending_fit_bounds
            self._pending_fit_bounds = False
            self._render(fit_bounds=fit_bounds)

    def _schedule_web_view_sync(self) -> None:
        if self.web_view is None or self._sync_pending:
            return
        self._sync_pending = True
        QTimer.singleShot(0, self._sync_web_view_geometry)
        QTimer.singleShot(100, self._sync_web_view_geometry)

    def _sync_web_view_geometry(self) -> None:
        self._sync_pending = False
        if self.web_view is None or self.web_view.parentWidget() is None:
            return
        target = QRect(0, 0, self.stack.width(), self.stack.height())
        if target.isValid() and self.web_view.geometry() != target:
            self.web_view.setGeometry(target)
        if self.stack.currentWidget() is self.web_view:
            self.web_view.raise_()
            self.web_view.update()

    def _aoi_geometry(self) -> dict[str, Any]:
        if self._criteria is None:
            return {}
        try:
            return aoi_geojson_from_inputs(
                self._criteria.aoi_mode,
                bbox=self._criteria.bbox,
                wkt=self._criteria.wkt,
                aoi_file=self._criteria.aoi_file,
            )
        except Exception:
            if self._criteria.bbox:
                try:
                    return aoi_geojson_from_inputs("bbox", bbox=self._criteria.bbox)
                except Exception:
                    return {}
        return {}

    def _payload(self, aoi_geometry: dict[str, Any], scenes: list[SceneRecord]) -> dict[str, Any]:
        scene_features = []
        highlighted_feature = None
        for scene in scenes:
            if not scene.footprint_geojson:
                continue
            feature = {
                "type": "Feature",
                "properties": {
                    "scene_id": scene.scene_id,
                    "selected": scene.scene_id in self._selected_scene_ids,
                    "highlighted": scene.scene_id == self._highlight_scene_id,
                },
                "geometry": scene.footprint_geojson,
            }
            if scene.scene_id == self._highlight_scene_id:
                highlighted_feature = feature
            else:
                scene_features.append(feature)
        if highlighted_feature is not None:
            scene_features.append(highlighted_feature)
        aoi_feature = (
            {"type": "Feature", "properties": {"name": "AOI"}, "geometry": aoi_geometry}
            if aoi_geometry
            else None
        )
        dem_feature = self._dem_feature()
        bounds = bounds_from_geojson(
            ([aoi_geometry] if aoi_geometry else [])
            + ([dem_feature["geometry"]] if dem_feature is not None else [])
            + [scene.footprint_geojson for scene in scenes]
        )
        return {
            "aoi": aoi_feature,
            "dem": dem_feature,
            "scenes": {"type": "FeatureCollection", "features": scene_features},
            "bounds": bounds,
        }

    def _leaflet_html(self, aoi_geometry: dict[str, Any], scenes: list[SceneRecord], *, fit_bounds: bool = True) -> str:
        payload = self._payload(aoi_geometry, scenes)
        escaped_payload = json.dumps(payload)
        should_fit_bounds = "true" if fit_bounds else "false"
        tianditu_enabled = "true" if self._tianditu_enabled else "false"
        tianditu_proxy_url = json.dumps(self._tianditu_proxy_url)
        preferred_basemap_name = json.dumps(self._preferred_basemap_name)
        leaflet_css = _read_text_asset("leaflet.css").replace("</style>", "<\\/style>")
        leaflet_js = _read_text_asset("leaflet.js").replace("</script>", "<\\/script>")
        title = html.escape("Sentinel-1 Footprint Map")
        return f"""<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <title>{title}</title>
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <style>
    {leaflet_css}
    html, body, #map {{ height: 100%; margin: 0; background: #f7f9fc; }}
    .fallback {{
      position: absolute;
      bottom: 12px;
      left: 12px;
      z-index: 999;
      max-width: 360px;
      background: rgba(255, 255, 255, 0.94);
      padding: 7px 9px;
      border: 1px solid #cfd7e3;
      border-radius: 4px;
      color: #344054;
      font: 13px sans-serif;
      box-shadow: 0 2px 10px rgba(16, 24, 40, 0.12);
    }}
  </style>
  <script>{leaflet_js}</script>
</head>
<body>
<div id="map"></div>
<script>
	let payload = {escaped_payload};
	const shouldFitBounds = {should_fit_bounds};
const tiandituEnabled = {tianditu_enabled};
const tiandituProxyUrl = {tianditu_proxy_url};
const preferredBasemapName = {preferred_basemap_name};
const map = L.map('map', {{ preferCanvas: true }}).setView([0, 0], 2);
function showNote(message) {{
  let note = document.querySelector('.fallback');
  if (!note) {{
    note = document.createElement('div');
    note.className = 'fallback';
    document.body.appendChild(note);
  }}
  note.textContent = message;
}}
function tiandituLayer(layerName, attribution) {{
  const layer = L.tileLayer(`${{tiandituProxyUrl}}/${{layerName}}/{{z}}/{{x}}/{{y}}`, {{
    maxZoom: 18,
    attribution
  }});
  return layer;
}}
const basemaps = {{}};
if (tiandituEnabled && tiandituProxyUrl) {{
  basemaps['Tianditu Imagery'] = L.layerGroup([
    tiandituLayer('img', 'Map data &copy; Tianditu'),
    tiandituLayer('cia', 'Map labels &copy; Tianditu')
  ]);
  basemaps['Tianditu Terrain'] = L.layerGroup([
    tiandituLayer('ter', 'Terrain &copy; Tianditu'),
    tiandituLayer('cta', 'Terrain labels &copy; Tianditu')
  ]);
}}
basemaps['External Imagery'] = L.tileLayer(
    `${{tiandituProxyUrl}}/esri_img/{{z}}/{{x}}/{{y}}`,
    {{ maxZoom: 18, attribution: 'Tiles &copy; Esri' }}
);
basemaps['External Terrain'] = L.tileLayer(
    `${{tiandituProxyUrl}}/esri_topo/{{z}}/{{x}}/{{y}}`,
    {{ maxZoom: 18, attribution: 'Tiles &copy; Esri' }}
);
let activeBasemapName = basemaps[preferredBasemapName] ? preferredBasemapName : 'External Imagery';
let activeBasemapLayer = null;
function activateBasemap(name) {{
  const nextLayer = basemaps[name] || basemaps['External Imagery'];
  if (!nextLayer) {{
    return;
  }}
  if (activeBasemapLayer && map.hasLayer(activeBasemapLayer)) {{
    map.removeLayer(activeBasemapLayer);
  }}
  activeBasemapName = name in basemaps ? name : 'External Imagery';
  activeBasemapLayer = nextLayer;
  activeBasemapLayer.addTo(map);
}}
const tileErrorCounts = {{}};
function registerTileErrors(name, layer) {{
  tileErrorCounts[name] = 0;
  if (layer.eachLayer) {{
    layer.eachLayer((childLayer) => registerTileErrors(name, childLayer));
    return;
  }}
  layer.on('tileerror', () => {{
    tileErrorCounts[name] += 1;
    if (name === activeBasemapName && tileErrorCounts[name] >= 4) {{
      if (name.startsWith('Tianditu') && basemaps['External Imagery']) {{
        activateBasemap('External Imagery');
        showNote('Tianditu basemap is unavailable right now. Switched to External Imagery; footprints remain visible.');
        return;
      }}
      showNote(`${{name}} basemap tiles could not be loaded. Try switching basemap; footprints remain visible.`);
    }}
  }});
}}
Object.entries(basemaps).forEach(([name, layer]) => {{
  registerTileErrors(name, layer);
}});
activateBasemap(activeBasemapName);
L.control.layers(basemaps, null, {{ position: 'topright', collapsed: false }}).addTo(map);
map.on('baselayerchange', (event) => {{
  activeBasemapName = event.name;
  activeBasemapLayer = event.layer;
}});
	let sceneLayer = null;
	let aoiLayer = null;
	let demLayer = null;
	function sceneStyle(feature) {{
	  if (feature.properties.highlighted) {{
	    return {{ color: '#f2c94c', weight: 4, fillColor: '#f2c94c', fillOpacity: 0.18 }};
	  }}
	  return {{ color: '#2d9cdb', weight: 1.8, fillColor: '#2d9cdb', fillOpacity: 0.0 }};
	}}
	function resetLayer(layer) {{
	  if (layer && map.hasLayer(layer)) {{
	    map.removeLayer(layer);
	  }}
	}}
	function renderPayload(fitBounds) {{
	  resetLayer(sceneLayer);
	  resetLayer(aoiLayer);
	  resetLayer(demLayer);
	  sceneLayer = null;
	  aoiLayer = null;
	  demLayer = null;
	  if (payload.scenes.features.length) {{
	    sceneLayer = L.geoJSON(payload.scenes, {{
	      style: sceneStyle,
	      onEachFeature: (feature, layer) => layer.bindTooltip(feature.properties.scene_id)
	    }}).addTo(map);
	  }}
	  if (payload.aoi) {{
	    aoiLayer = L.geoJSON(payload.aoi, {{
	      style: {{ color: '#d94343', weight: 3, fillColor: '#d94343', fillOpacity: 0.08 }}
	    }}).addTo(map);
	  }}
	  if (payload.dem) {{
	    demLayer = L.geoJSON(payload.dem, {{
	      style: {{ color: '#27ae60', weight: 2.5, dashArray: '8 6', fillColor: '#27ae60', fillOpacity: 0.0 }}
	    }}).addTo(map);
	  }}
	  if (fitBounds && payload.bounds) {{
	    map.fitBounds([[payload.bounds[1], payload.bounds[0]], [payload.bounds[3], payload.bounds[2]]], {{ padding: [20, 20] }});
	  }} else if (fitBounds) {{
	    map.setView([0, 0], 2);
	    showNote('No footprint geometry available for current results.');
	  }}
	}}
	window.updateHighlight = function(sceneId, selectedIds) {{
	  const selected = new Set(selectedIds || []);
	  payload.scenes.features.forEach((feature) => {{
	    feature.properties.selected = selected.has(feature.properties.scene_id);
	    feature.properties.highlighted = feature.properties.scene_id === sceneId;
	  }});
	  payload.scenes.features.sort((left, right) => {{
	    return (left.properties.highlighted === right.properties.highlighted) ? 0 : (left.properties.highlighted ? 1 : -1);
	  }});
	  renderPayload(false);
	}};
	window.updateDem = function(demFeature) {{
	  payload.dem = demFeature || null;
	  renderPayload(false);
	}};
	renderPayload(shouldFitBounds);
	</script>
	</body>
	</html>"""

    def _run_js(self, script: str) -> None:
        try:
            self.web_view.page().runJavaScript(script)  # type: ignore[union-attr]
        except Exception as exc:
            self.fallback_reason = f"Embedded map update failed; using geometry preview. {exc}"
            self._render_geometry_fallback(self._aoi_geometry())

    def _render_geometry_fallback(self, aoi_geometry: dict[str, Any]) -> None:
        scene_polygons: dict[str, list[tuple[float, float]]] = {}
        highlighted: dict[str, list[tuple[float, float]]] = {}
        for scene in self._scenes:
            polygons = polygons_from_geojson(scene.footprint_geojson)
            if not polygons:
                continue
            scene_polygons[scene.scene_id] = polygons[0]
            if scene.scene_id == self._highlight_scene_id:
                highlighted[scene.scene_id] = polygons[0]
        self.geometry_panel.set_plot(
            VerifyPlotData(
                aoi_geometries=polygons_from_geojson(aoi_geometry),
                bbox_snwe=None,
                iw_polygons=scene_polygons,
                selected_swaths=set(),
                dem_bbox_snwe=self._dem_bbox_snwe,
                highlighted_polygons=highlighted,
            )
        )

    @staticmethod
    def _bbox_geometry(bbox_snwe: tuple[float, float, float, float] | None) -> dict[str, Any]:
        if bbox_snwe is None:
            return {}
        south, north, west, east = bbox_snwe
        return {
            "type": "Polygon",
            "coordinates": [[
                [west, south],
                [east, south],
                [east, north],
                [west, north],
                [west, south],
            ]],
        }

    def _dem_feature(self) -> dict[str, Any] | None:
        dem_bbox = getattr(self, "_dem_bbox_snwe", None)
        if dem_bbox is None:
            return None
        return {
            "type": "Feature",
            "properties": {"name": "DEM coverage"},
            "geometry": self._bbox_geometry(dem_bbox),
        }
