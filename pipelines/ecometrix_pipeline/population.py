"""WorldPop population rasters (100 m, CC BY 4.0), read only for the study window.

  load_population  constrained 2020 (the baseline: where people live today)
  load_series      unconstrained yearly 2000-2020 (the history the demand forecast learns from)
These two products are different WorldPop models and are never mixed in one calculation.
"""
from __future__ import annotations
import os
import tempfile
import numpy as np
import rasterio
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


def load_series(cfg: dict, grid: StudyGrid, years=None) -> dict:
    """Yearly population per cell. Windowed reads only: each yearly file is about 1.7 GB, so a year that
    cannot be read is skipped and reported in `missing`, never filled in."""
    sc = cfg["population_series"]
    out: dict[int, np.ndarray] = {}
    missing: dict[int, str] = {}
    for y in years or sc["years"]:
        try:
            with _open_remote_or_local(sc["url_template"].format(year=y)) as src:
                arr, tr = _read_window(src, _padded(grid))
            out[int(y)] = window_pixels(arr, tr, grid)["per_cell"]
        except Exception as ex:
            missing[int(y)] = f"{type(ex).__name__}: {ex}"
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
