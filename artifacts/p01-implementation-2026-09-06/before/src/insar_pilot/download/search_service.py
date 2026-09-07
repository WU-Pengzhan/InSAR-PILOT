"""Search service used by the GUI download page."""

from __future__ import annotations

from insar_pilot.download.models import SceneRecord, SearchCriteria
from insar_pilot.download.network import NetworkConfig
from insar_pilot.download.providers import ASFProvider
from insar_pilot.download.scene_filter import filter_by_orbit_direction, filter_by_relative_orbit, sort_by_time


class SearchService:
    """Coordinate provider search and local scene filtering."""

    def __init__(self, provider: ASFProvider | None = None) -> None:
        self.provider = provider or ASFProvider()

    def search(self, criteria: SearchCriteria, network: NetworkConfig | None = None) -> list[SceneRecord]:
        """Search scenes for GUI display.

        The provider owns ASF API details; this service only returns internal
        scene records for GUI display and persistence.
        """

        scenes = self.provider.search(criteria) if network is None else self.provider.search(criteria, network=network)
        scenes = filter_by_orbit_direction(scenes, criteria.orbit_direction)
        scenes = filter_by_relative_orbit(scenes, criteria.relative_orbit)
        return sort_by_time(scenes, descending=False)
