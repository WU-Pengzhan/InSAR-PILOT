"""Reuse the legacy imagery proxy without exposing annotation or terrain layers."""

from collections import OrderedDict
from threading import Lock

from insar_pilot.download.network import NetworkConfig
from insar_pilot.download.tile_proxy import TiandituTileProxy


class ImageryTiles:
    def __init__(self) -> None:
        self.proxy = TiandituTileProxy(NetworkConfig(mode="direct"))
        self.cache: OrderedDict[tuple[int, int, int], tuple[str, bytes]] = OrderedDict()
        self.lock = Lock()

    def fetch(self, z: int, x: int, y: int) -> tuple[int, str, bytes]:
        if not 0 <= z <= 18 or not (0 <= x < 2**z and 0 <= y < 2**z):
            raise ValueError("Tile coordinates are outside the imagery grid.")
        key = z, x, y
        with self.lock:
            cached = self.cache.get(key)
            if cached:
                self.cache.move_to_end(key)
                return 200, *cached
        status, content_type, data = self.proxy.fetch_tile("esri_img", z, x, y)
        if status == 200 and content_type.startswith("image/") and len(data) <= 2 * 1024**2:
            with self.lock:
                self.cache[key] = (content_type, data)
                self.cache.move_to_end(key)
                while len(self.cache) > 64:
                    self.cache.popitem(last=False)
            return status, content_type, data
        return 502, "text/plain", b"Imagery unavailable. AOI and footprints remain usable."

    def close(self) -> None:
        self.proxy.session.close()
