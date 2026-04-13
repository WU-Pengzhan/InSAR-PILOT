from pathlib import Path

from isce2_gui.services.iw_recommendation import IwRecommendationService


def _write_annotation(path: Path, swath: str, south: float, north: float, west: float, east: float) -> None:
    xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<product>
  <adsHeader>
    <swath>IW{swath}</swath>
  </adsHeader>
  <pass>ASCENDING</pass>
  <geolocationGrid>
    <geolocationGridPointList count="4">
      <geolocationGridPoint>
        <line>0</line><pixel>0</pixel><latitude>{north}</latitude><longitude>{west}</longitude>
      </geolocationGridPoint>
      <geolocationGridPoint>
        <line>0</line><pixel>200</pixel><latitude>{north}</latitude><longitude>{east}</longitude>
      </geolocationGridPoint>
      <geolocationGridPoint>
        <line>100</line><pixel>0</pixel><latitude>{south}</latitude><longitude>{west}</longitude>
      </geolocationGridPoint>
      <geolocationGridPoint>
        <line>100</line><pixel>200</pixel><latitude>{south}</latitude><longitude>{east}</longitude>
      </geolocationGridPoint>
    </geolocationGridPointList>
  </geolocationGrid>
</product>
"""
    path.write_text(xml, encoding="utf-8")


def test_iw_recommendation_returns_multi_swath_overlap(tmp_path: Path):
    safe_dir = tmp_path / "scene.SAFE"
    annotation_dir = safe_dir / "annotation"
    annotation_dir.mkdir(parents=True)
    _write_annotation(annotation_dir / "s1a-iw1-slc-vv-x.xml", "1", 32.6, 34.3, -117.62, -116.34)
    _write_annotation(annotation_dir / "s1a-iw2-slc-vv-x.xml", "2", 32.7, 34.4, -118.56, -117.25)
    _write_annotation(annotation_dir / "s1a-iw3-slc-vv-x.xml", "3", 33.0, 34.6, -119.34, -118.17)

    bbox_snwe = "33.7788 33.9493 -118.2879 -118.0395"
    result = IwRecommendationService().recommend(str(safe_dir), bbox_snwe)

    assert result.recommended_swaths == "2 3"
    assert result.overlaps["1"] == 0.0
    assert result.overlaps["2"] > 0.0
    assert result.overlaps["3"] > 0.0
    assert result.pass_direction == "ascending"


def test_iw_recommendation_falls_back_when_no_overlap(tmp_path: Path):
    safe_dir = tmp_path / "scene.SAFE"
    annotation_dir = safe_dir / "annotation"
    annotation_dir.mkdir(parents=True)
    _write_annotation(annotation_dir / "s1a-iw1-slc-vv-x.xml", "1", 32.6, 34.3, -117.62, -116.34)
    _write_annotation(annotation_dir / "s1a-iw2-slc-vv-x.xml", "2", 32.7, 34.4, -118.56, -117.25)
    _write_annotation(annotation_dir / "s1a-iw3-slc-vv-x.xml", "3", 33.0, 34.6, -119.34, -118.17)

    bbox_snwe = "10 11 10 11"
    result = IwRecommendationService().recommend(str(safe_dir), bbox_snwe)

    assert result.recommended_swaths == "1 2 3"
    assert result.warnings


def test_iw_recommendation_extracts_auto_selected_bursts(tmp_path: Path):
    safe_dir = tmp_path / "scene.SAFE"
    annotation_dir = safe_dir / "annotation"
    annotation_dir.mkdir(parents=True)
    xml = """<?xml version="1.0" encoding="UTF-8"?>
<product>
  <adsHeader><swath>IW2</swath></adsHeader>
  <pass>ASCENDING</pass>
  <swathTiming>
    <linesPerBurst>100</linesPerBurst>
    <burstList count="3">
      <burst><azimuthTime>2022-01-01T00:00:00</azimuthTime></burst>
      <burst><azimuthTime>2022-01-01T00:00:10</azimuthTime></burst>
      <burst><azimuthTime>2022-01-01T00:00:20</azimuthTime></burst>
    </burstList>
  </swathTiming>
  <geolocationGrid>
    <geolocationGridPointList count="8">
      <geolocationGridPoint><line>0</line><pixel>0</pixel><latitude>34.0</latitude><longitude>-118.5</longitude></geolocationGridPoint>
      <geolocationGridPoint><line>0</line><pixel>100</pixel><latitude>34.0</latitude><longitude>-118.0</longitude></geolocationGridPoint>
      <geolocationGridPoint><line>100</line><pixel>0</pixel><latitude>33.8</latitude><longitude>-118.5</longitude></geolocationGridPoint>
      <geolocationGridPoint><line>100</line><pixel>100</pixel><latitude>33.8</latitude><longitude>-118.0</longitude></geolocationGridPoint>
      <geolocationGridPoint><line>200</line><pixel>0</pixel><latitude>33.6</latitude><longitude>-118.5</longitude></geolocationGridPoint>
      <geolocationGridPoint><line>200</line><pixel>100</pixel><latitude>33.6</latitude><longitude>-118.0</longitude></geolocationGridPoint>
      <geolocationGridPoint><line>300</line><pixel>0</pixel><latitude>33.4</latitude><longitude>-118.5</longitude></geolocationGridPoint>
      <geolocationGridPoint><line>300</line><pixel>100</pixel><latitude>33.4</latitude><longitude>-118.0</longitude></geolocationGridPoint>
    </geolocationGridPointList>
  </geolocationGrid>
</product>
"""
    (annotation_dir / "s1a-iw2-slc-vv-x.xml").write_text(xml, encoding="utf-8")

    result = IwRecommendationService().recommend(str(safe_dir), "33.55 33.85 -118.4 -118.1")

    assert result.recommended_swaths == "2"
    assert len(result.bursts["2"]) == 3
    assert result.auto_selected_bursts["2"] == [1, 2, 3]
    assert result.auto_selected_burst_bbox_snwe is not None
