"""Faithful Web AOI import; reject ambiguous multipart sources."""

import xml.etree.ElementTree as ET
from pathlib import Path

import shapefile
from rasterio.crs import CRS
from shapely.geometry import LineString, Point, Polygon, shape


def file_wkt(path: Path) -> str:
    if not path.is_file() or path.stat().st_size > 16 * 1024**2:
        raise ValueError("Choose a readable AOI file up to 16 MiB.")
    if path.suffix.lower() == ".shp":
        for suffix in (".prj", ".shx", ".dbf"):
            if not path.with_suffix(suffix).is_file():
                raise ValueError(f"Shapefile requires its {suffix} companion.")
        crs = CRS.from_wkt(path.with_suffix(".prj").read_text())
        if crs != CRS.from_epsg(4326):
            raise ValueError("Export this Shapefile in WGS84 / EPSG:4326 before importing.")
        with shapefile.Reader(str(path)) as reader:
            shapes = reader.shapes()
            if len(shapes) != 1:
                raise ValueError("Choose a single AOI feature; multiple features are not reduced to a bounding box.")
            geometry = shape(shapes[0].__geo_interface__)
    elif path.suffix.lower() == ".kml":
        tree = ET.parse(path)
        geometries = tree.findall(".//{*}Polygon") + tree.findall(".//{*}LineString") + tree.findall(".//{*}Point")
        if len(geometries) != 1:
            raise ValueError("Choose a single KML geometry; multipart selection is not reduced silently.")
        node = geometries[0]

        def coords(element):
            if element is None or not element.text:
                raise ValueError("KML coordinates are missing.")
            return [tuple(float(v) for v in token.split(",")[:2]) for token in element.text.split()]

        kind = node.tag.split("}")[-1]
        if kind == "Polygon":
            outer = coords(node.find("./{*}outerBoundaryIs/{*}LinearRing/{*}coordinates"))
            holes = [coords(n) for n in node.findall("./{*}innerBoundaryIs/{*}LinearRing/{*}coordinates")]
            geometry = Polygon(outer, holes)
        else:
            points = coords(node.find("./{*}coordinates"))
            geometry = Point(points[0]) if kind == "Point" and len(points) == 1 else LineString(points)
    else:
        raise ValueError("AOI file must be KML or Shapefile.")
    if geometry.geom_type not in {"Point", "LineString", "Polygon"}:
        raise ValueError("Choose a single geometry; multipart AOIs must be split explicitly.")
    return str(geometry.wkt)
