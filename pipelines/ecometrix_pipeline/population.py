"""WorldPop population rasters (100 m, CC BY 4.0), read only for the study window.

  load_population  constrained 2020 (the baseline: where people live today)
  load_series      unconstrained yearly 2000-2020 (the history the demand forecast learns from)
These two products are different WorldPop models and are never mixed in one calculation.
"""
from __future__ import annotations
import os
from pathlib import Path
import numpy as np
import rasterio
from rasterio.windows import from_bounds
from .config import REPO_ROOT
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


def _download_population(url: str, sess, cache_path: Path) -> None:
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    partial_path = cache_path.with_suffix(cache_path.suffix + ".part")
    downloaded = 0
    expected_size = None
    print(f"Downloading WorldPop raster to {cache_path} (the source does not support windowed HTTP reads).",
          flush=True)
    try:
        with sess.get(url, stream=True, timeout=600) as response:
            response.raise_for_status()
            content_length = response.headers.get("Content-Length")
            expected_size = int(content_length) if content_length else None
            with partial_path.open("wb") as target:
                for chunk in response.iter_content(1 << 22):
                    if chunk:
                        target.write(chunk)
                        downloaded += len(chunk)
                        if downloaded % (64 << 20) < len(chunk):
                            size = f"{downloaded / (1 << 20):.0f} MiB"
                            if expected_size:
                                size += f" / {expected_size / (1 << 20):.0f} MiB"
                            print(f"  WorldPop download: {size}", flush=True)
        if expected_size is not None and downloaded != expected_size:
            raise IOError(f"WorldPop download was incomplete: received {downloaded} of {expected_size} bytes")
        partial_path.replace(cache_path)
    finally:
        partial_path.unlink(missing_ok=True)


def load_population(
    cfg: dict,
    grid: StudyGrid,
    sess,
    local_path: str | None = None,
    cache_path: str | Path | None = None,
) -> dict:
    """Constrained 2020 baseline: pixel centres (metric), people per pixel and per-cell totals."""
    bbox = _padded(grid)
    url = cfg["population"]["url"]
    how = "windowed read over HTTP"
    if local_path:
        with rasterio.open(local_path) as src:
            arr, tr = _read_window(src, bbox)
        how = "local file"
    else:
        cache = Path(cache_path) if cache_path else (
            REPO_ROOT / "data" / "raw" / "population" / "ind_ppp_2020_constrained.tif"
        )
        if cache.exists():
            with rasterio.open(cache) as src:
                arr, tr = _read_window(src, bbox)
            how = "cached local file (downloaded after windowed HTTP read failed)"
        else:
            try:
                with _open_remote_or_local(url) as src:
                    arr, tr = _read_window(src, bbox)
            except rasterio.errors.RasterioIOError as exc:
                if "Range downloading not supported" not in str(exc):
                    raise
                _download_population(url, sess, cache)
                with rasterio.open(cache) as src:
                    arr, tr = _read_window(src, bbox)
                how = f"cached full download (windowed HTTP read failed: {exc})"
    res = window_pixels(arr, tr, grid)
    res["how"] = how
    return res
