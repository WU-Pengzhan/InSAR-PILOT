from pathlib import Path
from zipfile import ZipFile

from insar_pilot.services.input_catalog import InputCatalogService


MANIFEST_TEMPLATE = """<?xml version="1.0" encoding="UTF-8"?>
<xfdu:XFDU xmlns:xfdu="urn:ccsds:schema:xfdu:1" xmlns:safe="http://www.esa.int/safe/sentinel-1.0">
  <metadataSection>
    <metadataObject ID="processing">
      <metadataWrap>
        <xmlData>
          <safe:processing>
            <safe:facility site="TEST" country="TEST">
              <safe:software name="IPF" version="{version}" />
            </safe:facility>
          </safe:processing>
        </xmlData>
      </metadataWrap>
    </metadataObject>
  </metadataSection>
</xfdu:XFDU>
"""


def test_scan_detects_aux_requirement(tmp_path: Path):
    safe_dir = tmp_path / "S1_TEST.SAFE"
    safe_dir.mkdir()
    (safe_dir / "manifest.safe").write_text(MANIFEST_TEMPLATE.format(version="002.36"), encoding="utf-8")

    report = InputCatalogService().scan(tmp_path)

    assert len(report.entries) == 1
    assert report.entries[0].kind == "safe"
    assert report.aux_required is True


def test_scan_recurses_into_download_date_folders(tmp_path: Path):
    day_dir = tmp_path / "20240101"
    day_dir.mkdir()
    zip_path = day_dir / "S1_TEST_SAFE.zip"
    with ZipFile(zip_path, "w") as archive:
        archive.writestr("S1_TEST.SAFE/manifest.safe", MANIFEST_TEMPLATE.format(version="003.10"))

    report = InputCatalogService().scan(tmp_path)

    assert len(report.entries) == 1
    assert report.entries[0].path == str(zip_path)
    assert report.entries[0].kind == "zip"


def test_prepare_inputs_extracts_zip_and_writes_manifest(tmp_path: Path):
    source_dir = tmp_path / "source"
    source_dir.mkdir()
    zip_path = source_dir / "S1_TEST_SAFE.zip"
    with ZipFile(zip_path, "w") as archive:
        archive.writestr("S1_TEST.SAFE/manifest.safe", MANIFEST_TEMPLATE.format(version="003.10"))

    service = InputCatalogService()
    report = service.scan(source_dir)

    class Workflow:
        extract_zips = True
        extract_dir = str(tmp_path / "extracted")

        def resolved_extract_dir(self):
            return Path(self.extract_dir)

    prepared = service.prepare_inputs(Workflow(), tmp_path / "work", report)

    manifest = Path(prepared.manifest_path)
    assert manifest.exists()
    lines = manifest.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1
    assert lines[0].endswith(".SAFE")
    assert Path(lines[0]).exists()
