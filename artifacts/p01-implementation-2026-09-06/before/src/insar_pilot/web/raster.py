"""Bounded raster reads for scientific images and georeferenced Web tiles."""

from __future__ import annotations

import io
import math
from typing import Any


def _read(artifact: dict[str, Any]) -> Any:
    import numpy as np

    path = artifact["assets"][0]["uri"]
    dataset = artifact.get("metadata", {}).get("phase_dataset")
    if dataset:
        import h5py

        with h5py.File(path, "r") as handle:
            source = handle[dataset]
            stride = max(1, math.ceil(max(source.shape) / 1536))
            array = source[::stride, ::stride]
    else:
        import rasterio

        with rasterio.open(path) as source:
            ratio = min(1, 1536 / max(source.width, source.height))
            array = source.read(
                1, out_shape=(max(1, int(source.height * ratio)), max(1, int(source.width * ratio))), masked=True
            ).filled(np.nan)
    return np.angle(array).astype("float32") if np.iscomplexobj(array) else np.asarray(array, dtype="float32")


def display_range(array: Any) -> tuple[float, float]:
    import numpy as np

    finite = array[np.isfinite(array)]
    low, high = np.percentile(finite, [2, 98]) if finite.size else (0, 1)
    return float(low), float(high)


def _png(array: Any, limits: tuple[float, float] | None = None) -> bytes:
    import numpy as np
    from PIL import Image

    valid = np.isfinite(array)
    low, high = limits if limits is not None else display_range(array)
    values = np.nan_to_num(np.clip((array - low) / max(float(high - low), 1e-10), 0, 1))
    # Blue–cyan–yellow ramp, with transparent invalid samples.
    rgb = np.stack(
        [values * 255, np.sin(values * np.pi / 2) * 255, (1 - values) * 230, valid.astype(float) * 255], axis=-1
    ).astype("uint8")
    stream = io.BytesIO()
    Image.fromarray(rgb).save(stream, "PNG")
    return stream.getvalue()


def preview_png(artifact: dict[str, Any]) -> bytes:
    return _png(_read(artifact))


def pixel_value(artifact: dict[str, Any], row: int, column: int) -> dict[str, Any]:
    import numpy as np

    path = artifact["assets"][0]["uri"]
    dataset = artifact.get("metadata", {}).get("phase_dataset")
    if row < 0 or column < 0:
        raise ValueError("Pixel coordinates must be nonnegative.")
    if dataset:
        import h5py

        with h5py.File(path, "r") as handle:
            source = handle[dataset]
            if row >= source.shape[0] or column >= source.shape[1]:
                raise ValueError("Pixel is outside the artifact grid.")
            value = source[row, column]
    else:
        import rasterio
        from rasterio.windows import Window

        with rasterio.open(path) as source:
            if row >= source.height or column >= source.width:
                raise ValueError("Pixel is outside the artifact grid.")
            value = source.read(1, window=Window(column, row, 1, 1), masked=True)[0, 0]
            if np.ma.is_masked(value):
                value = np.nan
    valid = bool(np.isfinite(value))
    raw = (
        {"real": float(value.real), "imaginary": float(value.imag)}
        if np.iscomplexobj(value) and valid
        else float(value)
        if valid
        else None
    )
    return {
        "row": row,
        "column": column,
        "value": raw,
        "valid": valid,
        "phase_rad": float(np.angle(value)) if valid and np.iscomplexobj(value) else None,
        "unit": artifact.get("metadata", {}).get("unit"),
        "artifact_id": artifact["artifact_id"],
    }


def tile_png(artifact: dict[str, Any], z: int, x: int, y: int) -> bytes:
    import numpy as np
    from rasterio.transform import from_bounds
    from rasterio.warp import Resampling, reproject

    spatial = artifact.get("spatial", {})
    if spatial.get("grid_kind") != "map" or not spatial.get("crs") or not spatial.get("bounds"):
        raise ValueError("This artifact has no validated map grid; use the image workspace.")
    if not 0 <= z <= 22 or not 0 <= x < 2**z or not 0 <= y < 2**z:
        raise ValueError("Invalid tile coordinate.")
    source = _read(artifact)
    radius = 20037508.342789244
    width = 2 * radius / 2**z
    bounds = (-radius + x * width, radius - (y + 1) * width, -radius + (x + 1) * width, radius - y * width)
    output = np.full((256, 256), np.nan, dtype="float32")
    reproject(
        source,
        output,
        src_transform=from_bounds(*spatial["bounds"], source.shape[1], source.shape[0]),
        src_crs=spatial["crs"],
        dst_transform=from_bounds(*bounds, 256, 256),
        dst_crs="EPSG:3857",
        src_nodata=np.nan,
        dst_nodata=np.nan,
        resampling=Resampling.nearest,
    )
    # A value has the same color across every tile and zoom level.
    return _png(output, display_range(source))
