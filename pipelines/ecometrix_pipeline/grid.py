"""One shared spatial frame for every layer: an H3 hexagon grid plus a 30 m metric pixel grid.

All rasters are resampled onto the pixel grid; each pixel is mapped to the hexagon that contains it,
so any layer can be summarised per hexagon with a simple weighted bincount.
"""
from __future__ import annotations
from dataclasses import dataclass
import numpy as np
import pandas as pd
from h3.api import basic_int as h3i
from pyproj import Transformer
from rasterio.transform import Affine
from shapely.geometry import shape, box
import shapely


def project(geom, transformer: Transformer):
    """Reproject any shapely geometry with a pyproj transformer (always_xy)."""
    def f(coords):
        x, y = transformer.transform(coords[:, 0], coords[:, 1])
        return np.column_stack([x, y])
    return shapely.transform(geom, f)


def latlng_to_cells(lat: np.ndarray, lng: np.ndarray, res: int) -> np.ndarray:
    lat = np.asarray(lat, dtype=float).ravel()
    lng = np.asarray(lng, dtype=float).ravel()
    f = h3i.latlng_to_cell
    return np.fromiter((f(a, b, res) for a, b in zip(lat, lng)), dtype=np.uint64, count=lat.size)


def polygon_to_cells(geom, res: int) -> np.ndarray:
    """H3 cells whose centre falls inside the (WGS84) polygon or multipolygon."""
    polys = [geom] if geom.geom_type == "Polygon" else list(geom.geoms)
    cells: set[int] = set()
    for p in polys:
        cells.update(h3i.geo_to_cells(p.__geo_interface__, res))
    return np.array(sorted(cells), dtype=np.uint64)


def cell_polygon_utm(cell: int, to_utm: Transformer):
    ring = h3i.cell_to_boundary(cell)  # ((lat, lng), ...)
    poly = shape({"type": "Polygon", "coordinates": [[(lng, lat) for lat, lng in ring]]})
    return project(poly, to_utm)


@dataclass
class StudyGrid:
    res: int
    epsg: int
    pixel_m: int
    boundary: object                 # shapely geometry in WGS84
    cells: np.ndarray                # uint64 H3 ids inside the boundary
    transform: Affine                # pixel grid, metric CRS
    shape: tuple[int, int]           # (height, width)
    to_utm: Transformer
    to_wgs: Transformer
    pixel_cell_idx: np.ndarray       # (h, w) int32: index into `cells`, or -1 if outside

    @property
    def n_cells(self) -> int:
        return int(self.cells.size)

    @property
    def bbox_wgs(self) -> tuple[float, float, float, float]:
        return tuple(self.boundary.bounds)  # type: ignore[return-value]

    def hex_ids(self) -> list[str]:
        return [h3i.int_to_str(int(c)) for c in self.cells]

    def centroids(self) -> tuple[np.ndarray, np.ndarray]:
        ll = [h3i.cell_to_latlng(int(c)) for c in self.cells]
        return np.array([a for a, _ in ll]), np.array([b for _, b in ll])

    def geobox(self, factor: int = 1):
        """odc-geo GeoBox for loading STAC rasters exactly onto this grid (factor>1 = finer grid)."""
        from odc.geo.geobox import GeoBox
        h, w = self.shape
        aff = self.transform * Affine.scale(1.0 / factor, 1.0 / factor)
        return GeoBox((h * factor, w * factor), aff, f"EPSG:{self.epsg}")

    def zonal_mean(self, arr: np.ndarray, valid: np.ndarray | None = None) -> tuple[np.ndarray, np.ndarray]:
        """Mean of `arr` over the pixels of each hexagon, and the count of valid pixels used."""
        idx = self.pixel_cell_idx.ravel()
        a = np.asarray(arr, dtype=float).ravel()
        ok = (idx >= 0) & np.isfinite(a)
        if valid is not None:
            ok &= np.asarray(valid, dtype=bool).ravel()
        n = self.n_cells
        sums = np.bincount(idx[ok], weights=a[ok], minlength=n)
        cnt = np.bincount(idx[ok], minlength=n)
        with np.errstate(invalid="ignore", divide="ignore"):
            mean = np.where(cnt > 0, sums / np.maximum(cnt, 1), np.nan)
        return mean, cnt


def build_grid(boundary, res: int, epsg: int, pixel_m: int) -> StudyGrid:
    to_utm = Transformer.from_crs(4326, epsg, always_xy=True)
    to_wgs = Transformer.from_crs(epsg, 4326, always_xy=True)
    cells = polygon_to_cells(boundary, res)
    if cells.size == 0:
        raise ValueError("Boundary produced no H3 cells; check the boundary geometry.")
    # extent: cell footprints (so edge hexagons are fully covered), snapped to the pixel grid
    lats, lngs = [], []
    for c in cells:
        for lat, lng in h3i.cell_to_boundary(int(c)):
            lats.append(lat); lngs.append(lng)
    xs, ys = to_utm.transform(np.array(lngs), np.array(lats))
    minx = np.floor(xs.min() / pixel_m) * pixel_m
    maxx = np.ceil(xs.max() / pixel_m) * pixel_m
    miny = np.floor(ys.min() / pixel_m) * pixel_m
    maxy = np.ceil(ys.max() / pixel_m) * pixel_m
    w = int(round((maxx - minx) / pixel_m))
    h = int(round((maxy - miny) / pixel_m))
    transform = Affine(pixel_m, 0, minx, 0, -pixel_m, maxy)
    cx = minx + (np.arange(w) + 0.5) * pixel_m
    cy = maxy - (np.arange(h) + 0.5) * pixel_m
    gx, gy = np.meshgrid(cx, cy)
    lng, lat = to_wgs.transform(gx.ravel(), gy.ravel())
    pix_cells = latlng_to_cells(lat, lng, res)
    idx = pd.Index(cells).get_indexer(pix_cells).astype(np.int32).reshape(h, w)
    return StudyGrid(res, epsg, pixel_m, boundary, cells, transform, (h, w), to_utm, to_wgs, idx)
