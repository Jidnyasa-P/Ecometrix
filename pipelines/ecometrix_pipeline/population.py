"""WorldPop population rasters (100 m, CC BY 4.0), read only for the study window.

  load_population  constrained 2020 (the baseline: where people live today)
  load_series      unconstrained yearly 2000-2020 (the history the demand forecast learns from)
These two products are different WorldPop models and are never mixed in one calculation.
"""
from __future__ import annotations
import os
import tempfile
from datetime import datetime, timezone
import numpy as np
import rasterio
import requests
from rasterio.io import MemoryFile
from rasterio.windows import from_bounds
from .grid import StudyGrid, latlng_to_cells


def _read_window(src, bbox):
    w, s, e, n = bbox
    win = from_bounds(w, s, e, n, transform=src.transform).round_offsets().round_lengths()
    arr = src.read(1, window=win, masked=True)
    tr = src.window_transform(win)
    return arr, tr


def window_pixels(arr, tr, grid: StudyGrid) -> dict:
    """People per pixel (positive values inside the study cells) with cell index and metric coordinates."""
    h, w = arr.shape
    cols, rows = np.meshgrid(np.arange(w), np.arange(h))
    xs, ys = rasterio.transform.xy(tr, rows.ravel(), cols.ravel(), offset="center")
    lon, lat = np.asarray(xs), np.asarray(ys)
    vals = np.ma.filled(arr.astype("float64"), np.nan).ravel()
    ok = np.isfinite(vals) & (vals > 0)
    lon, lat, vals = lon[ok], lat[ok], vals[ok]
    cell_ids = latlng_to_cells(lat, lon, grid.res)
    idx = np.searchsorted(grid.cells, cell_ids)
    idx[idx >= grid.n_cells] = 0
    inside = grid.cells[idx] == cell_ids
    lon, lat, vals, idx = lon[inside], lat[inside], vals[inside], idx[inside]
    x, y = grid.to_utm.transform(lon, lat)
    return {"xy": np.column_stack([x, y]), "people": vals, "cell_idx": idx,
            "per_cell": np.bincount(idx, weights=vals, minlength=grid.n_cells),
            "total": float(vals.sum()), "pixels": int(vals.size)}


def _padded(grid: StudyGrid, pad=0.01):
    w, s, e, n = grid.bbox_wgs
    return (w - pad, s - pad, e + pad, n + pad)


def _open_remote_or_local(url: str):
    if url.startswith("http"):
        os.environ.setdefault("GDAL_DISABLE_READDIR_ON_OPEN", "EMPTY_DIR")
        os.environ.setdefault("CPL_VSIL_CURL_ALLOWED_EXTENSIONS", ".tif")
        return rasterio.open(f"/vsicurl/{url}")
    return rasterio.open(url)


def _read_arcgis_series_window(sc: dict, grid: StudyGrid, year: int, sess=None):
    """Export one native-resolution year from WorldPop's cloud-optimised ImageServer.

    The public data.worldpop.org GeoTIFF host may reject HTTP byte-range requests, which
    prevents GDAL's /vsicurl reader from opening the large national raster. The ImageServer
    serves the same WorldPop annual 100 m estimates and can export just the study-area window.
    """
    service_url = sc.get("arcgis_export_url")
    if not service_url:
        raise RuntimeError("no ArcGIS ImageServer fallback is configured")

    bbox = _padded(grid)
    west, south, east, north = bbox
    pixel_size = float(sc.get("pixel_size_deg", 1.0 / 1200.0))
    if pixel_size <= 0:
        raise ValueError("population_series.pixel_size_deg must be positive")
    width = max(1, int(round((east - west) / pixel_size)))
    height = max(1, int(round((north - south) / pixel_size)))

    # ArcGIS ImageServer time values are milliseconds since the Unix epoch.
    instant = int(datetime(int(year), 1, 1, tzinfo=timezone.utc).timestamp() * 1000)
    params = {
        "bbox": f"{west},{south},{east},{north}",
        "bboxSR": 4326,
        "imageSR": 4326,
        "size": f"{width},{height}",
        "time": str(instant),
        "format": "tiff",
        "pixelType": "F32",
        "interpolation": "RSP_NearestNeighbor",
        "f": "image",
    }
    client = sess or requests
    response = client.get(service_url, params=params, timeout=(20, 180))
    try:
        response.raise_for_status()
        content_type = response.headers.get("Content-Type", "").lower()
        if "json" in content_type or not response.content:
            try:
                detail = response.json()
            except Exception:
                detail = response.text[:500]
            raise RuntimeError(f"WorldPop ImageServer did not return a raster: {detail}")
        with MemoryFile(response.content) as memfile:
            with memfile.open() as src:
                return _read_window(src, bbox)
    finally:
        response.close()


def load_series(cfg: dict, grid: StudyGrid, years=None, sess=None) -> dict:
    """Yearly population per cell, preferring windowed GeoTIFF reads and falling back to
    study-area exports when the source server does not support HTTP byte ranges. A year
    that cannot be read from either source is reported in `missing`, never filled in."""
    sc = cfg["population_series"]
    out: dict[int, np.ndarray] = {}
    missing: dict[int, str] = {}
    for y in years or sc["years"]:
        year = int(y)
        primary_error = None
        try:
            with _open_remote_or_local(sc["url_template"].format(year=year)) as src:
                arr, tr = _read_window(src, _padded(grid))
        except Exception as ex:
            primary_error = ex
            source_url = sc["url_template"].format(year=year)
            if not source_url.startswith(("http://", "https://")):
                missing[year] = f"{type(primary_error).__name__}: {primary_error}"
                continue
            try:
                arr, tr = _read_arcgis_series_window(sc, grid, year, sess=sess)
            except Exception as fallback_error:
                missing[year] = (f"{type(primary_error).__name__}: {primary_error}; "
                                 f"ArcGIS fallback: {type(fallback_error).__name__}: {fallback_error}")
                continue
        out[year] = window_pixels(arr, tr, grid)["per_cell"]
    return {"per_cell_by_year": out, "missing": missing}


def load_population(cfg: dict, grid: StudyGrid, sess, local_path: str | None = None) -> dict:
    """Constrained 2020 baseline: pixel centres (metric), people per pixel and per-cell totals."""
    bbox = _padded(grid)
    url = cfg["population"]["url"]
    how = "windowed read over HTTP"
    tmp = None
    try:
        if local_path:
            src = rasterio.open(local_path); how = "local file"
        else:
            src = _open_remote_or_local(url)
        with src:
            arr, tr = _read_window(src, bbox)
    except Exception as e_http:
        # fall back to a full download (about 0.5 GB); fine on a CI runner
        tmp = tempfile.NamedTemporaryFile(suffix=".tif", delete=False)
        with sess.get(url, stream=True, timeout=600) as r:
            r.raise_for_status()
            for chunk in r.iter_content(1 << 22):
                tmp.write(chunk)
        tmp.close()
        how = f"full download (windowed read failed: {e_http!r})"
        with rasterio.open(tmp.name) as src:
            arr, tr = _read_window(src, bbox)
    finally:
        if tmp is not None:
            try: os.unlink(tmp.name)
            except OSError: pass
    res = window_pixels(arr, tr, grid)
    res["how"] = how
    return res
