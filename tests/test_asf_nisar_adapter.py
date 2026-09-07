from __future__ import annotations

from datetime import datetime, timezone

import pytest

from insar_pilot.domain.search import SearchRequest
from insar_pilot.download.network import NetworkConfig
from insar_pilot.providers.sar import ASFNisarSearchProvider, build_default_sar_provider_registry


class _Product:
    properties = {
        "sceneName": "NISAR_L1_PR_RSLC_TEST",
        "fileName": "NISAR_L1_PR_RSLC_TEST.h5",
        "platform": "NISAR",
        "processingLevel": "RSLC",
        "startTime": "2026-07-01T01:02:03Z",
        "stopTime": "2026-07-01T01:03:03Z",
        "flightDirection": "DESCENDING",
        "pathNumber": 13,
        "frameNumber": 71,
        "orbit": 4005,
        "mainBandPolarization": ["HH", "HV"],
        "sideBandPolarization": ["HH"],
        "rangeBandwidth": ["40+5"],
        "productionConfiguration": "PR",
        "dataMaturity": "PROVISIONAL",
        "frameCoverage": "Full",
        "jointObservation": True,
        "collectionName": "NISAR_L1_RSLC_PROVISIONAL_V1",
        "url": "https://example.test/NISAR_L1_PR_RSLC_TEST.h5",
        "bytes": {
            "NISAR_L1_PR_RSLC_TEST.h5": {"bytes": 29_000_000_000, "format": "HDF5"},
        },
    }

    def geojson(self):
        return {
            "type": "Feature",
            "geometry": {"type": "Polygon", "coordinates": [[[0, 0], [1, 0], [0, 1], [0, 0]]]},
            "properties": self.properties,
        }

    def get_urls(self):
        return [self.properties["url"]]


def _request(**overrides) -> SearchRequest:
    values = {
        "mission": "NISAR",
        "platforms": ("NISAR",),
        "product_type": "RSLC",
        "start_time": datetime(2026, 6, 1, tzinfo=timezone.utc),
        "end_time": datetime(2026, 8, 1, tzinfo=timezone.utc),
        "aoi_wkt": "POLYGON((0 0,1 0,1 1,0 0))",
        "orbit_direction": "DESCENDING",
        "relative_orbit": 13,
        "polarizations": ("HH",),
        "frequency_bands": ("A",),
        "page_size": 10,
        "provider_options": {
            "asf-nisar": {
                "frame": 71,
                "production_configuration": "PR",
                "joint_observation": True,
            }
        },
    }
    values.update(overrides)
    return SearchRequest(**values)


def test_nisar_adapter_maps_aoi_query_and_portable_result(monkeypatch):
    observed = {}

    def _search(**kwargs):
        observed.update(kwargs)
        return [_Product()]

    monkeypatch.setattr("insar_pilot.providers.sar.asf_nisar.asf.geo_search", _search)
    page = ASFNisarSearchProvider(network=NetworkConfig(mode="direct")).search(_request())

    assert observed["platform"] == "NISAR"
    assert observed["processingLevel"] == "RSLC"
    assert observed["intersectsWith"].startswith("POLYGON")
    assert observed["frame"] == 71
    assert observed["productionConfiguration"] == "PR"
    assert "mainBandPolarization" not in observed
    assert "sideBandPolarization" not in observed
    product = page.items[0]
    assert product.frequency_bands == ("A", "B")
    assert product.polarizations == ("HH", "HV")
    assert product.relative_orbit == 13
    assert product.size_bytes == 29_000_000_000
    assert product.provider_metadata["frame_number"] == 71
    assert not hasattr(product, "properties")


@pytest.mark.parametrize(
    "options",
    [
        {"production_configuration": "INVALID"},
        {"frame": 0},
        {"joint_observation": "yes"},
    ],
)
def test_nisar_adapter_rejects_invalid_provider_options(options):
    request = _request(provider_options={"asf-nisar": options})
    report = ASFNisarSearchProvider().supports(request)
    assert not report.supported
    assert report.reason_code == "unsupported_provider_option"


def test_default_registry_exposes_production_nisar_rslc_only():
    descriptors = build_default_sar_provider_registry().descriptors()
    nisar = next(item for item in descriptors if item.provider_id == "asf-nisar")
    assert nisar.missions == ("NISAR",)
    assert nisar.search_capabilities[0].product_types == ("RSLC",)
