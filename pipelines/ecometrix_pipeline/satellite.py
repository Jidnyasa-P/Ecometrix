"""Satellite layers from STAC catalogues.

The stable model inputs remain multi-year pre-monsoon composites for fair seasonal
comparison. Separate rolling-window Landsat LST and Sentinel-2 NDVI layers are queried
every build to expose the latest published observations in the dashboard. These are
near-real-time observations, not a live sensor feed. LST is surface temperature, not air
or human-exposure temperature.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
import numpy as np
from .grid import StudyGrid

LANDSAT_SCALE, LANDSAT_OFFSET = 0.00341802, 149.0    # Collection 2 Level-2 surface temperature, DN -> kelvin
WORLDCOVER_CLASSES = {10: "treecover_pct", 20: "shrub_pct", 30: "grass_pct", 40: "crop_pct",
                      50: "builtup_pct", 60: "bare_pct", 80: "water_pct"}


def open_catalog(cfg: dict):
    import planetary_computer
    from pystac_client import Client
    return Client.open(cfg["satellite"]["stac_url"], modifier=planetary_computer.sign_inplace)


def _season_ranges(cfg: dict, years=None):
    m = cfg["satellite"]["season_months"]
    out = []
    for y in years or cfg["satellite"]["years"]:
        out.append(f"{y}-{min(m):02d}-01/{y}-{max(m):02d}-31")
    return out


def latest_ranges(cfg: dict, as_of: date | None = None) -> list[str]:
    """Inclusive rolling window ending today (UTC), so each scheduled build checks new data."""
    end = as_of or datetime.now(timezone.utc).date()
    days = int(cfg["satellite"].get("latest_window_days", 180))
    if days < 1:
        raise ValueError("satellite.latest_window_days must be at least 1")
    start = end - timedelta(days=days - 1)
    return [f"{start.isoformat()}/{end.isoformat()}"]


def search_items(cat, collection: str, bbox, ranges, extra_query=None) -> list:
    seen, items = set(), []
    for rng in ranges:
        s = cat.search(collections=[collection], bbox=list(bbox), datetime=rng, query=extra_query or {})
        for it in s.items():
            if it.id not in seen:
                seen.add(it.id)
                items.append(it)
    # STAC item datetimes can be a mix of naive and timezone-aware values. Search
    # results are already constrained by the requested interval; retaining their
    # provider order avoids unsafe datetime comparisons and preserves pagination order.
    return items


def _observation_dates(ds) -> tuple[list[str], str, str]:
    dates = sorted({str(t)[:10] for t in ds["time"].values})
    if not dates:
        raise RuntimeError("STAC items were returned but the raster has no acquisition dates")
    return dates, dates[0], dates[-1]


def scene_counts(cfg: dict, grid: StudyGrid, cat=None) -> dict:
    """Usable (cloud-filtered) pre-monsoon scene counts per year: the audit's coverage check."""
    cat = cat or open_catalog(cfg)
    cc = {"eo:cloud_cover": {"lt": cfg["satellite"]["cloud_cover_max"]}}
    out = {"landsat": {}, "sentinel2": {}}
    for y in cfg["satellite"]["audit_years"]:
        r = _season_ranges(cfg, [y])
        ls = search_items(cat, "landsat-c2-l2", grid.bbox_wgs, r, {**cc, "platform": {"in": ["landsat-8", "landsat-9"]}})
        s2 = search_items(cat, "sentinel-2-l2a", grid.bbox_wgs, r, cc)
        out["landsat"][str(y)] = len(ls)
        out["sentinel2"][str(y)] = len(s2)
    return out


def worldcover(cfg: dict, grid: StudyGrid, cat=None) -> dict:
    """Static ESA WorldCover reference layer (only 2020 and 2021 editions exist)."""
    import odc.stac
    cat = cat or open_catalog(cfg)
    items = search_items(cat, "esa-worldcover", grid.bbox_wgs, ["2020-01-01/2025-12-31"])
    if not items:
        raise RuntimeError("No ESA WorldCover items found for the study area")
    versions = sorted({it.properties.get("esa_worldcover:version", "?") for it in items})
    best = max(versions)
    chosen = [it for it in items if it.properties.get("esa_worldcover:version", "?") == best]
    year = sorted({(it.datetime or it.common_metadata.start_datetime).year for it in chosen})
    gb10 = grid.geobox(factor=3)
    ds = odc.stac.load(chosen, bands=["map"], geobox=gb10, resampling="nearest", chunks={})
    arr = ds["map"].isel(time=0).values if "time" in ds["map"].dims else ds["map"].values
    h, w = grid.shape
    blocks = arr.reshape(h, 3, w, 3)
    out = {}
    valid = (arr > 0).reshape(h, 3, w, 3).mean(axis=(1, 3)) > 0
    for code, name in WORLDCOVER_CLASSES.items():
        frac = (blocks == code).mean(axis=(1, 3))
        mean, _ = grid.zonal_mean(frac * 100.0, valid=valid)
        out[name] = mean
    return {"layers": out, "version": best, "years": year, "items": len(chosen)}


def landsat_lst(cfg: dict, grid: StudyGrid, cat=None, ranges=None, latest=False) -> dict:
    """Cloud-masked Landsat LST median over pre-monsoon or caller-supplied date ranges."""
    import odc.stac
    cat = cat or open_catalog(cfg)
    cloud_limit = cfg["satellite"].get("latest_cloud_cover_max", 70) if latest else cfg["satellite"]["cloud_cover_max"]
    min_obs = cfg["satellite"].get("latest_min_clear_obs", 1) if latest else cfg["satellite"]["min_clear_obs"]
    cc = {"eo:cloud_cover": {"lt": cloud_limit},
          "platform": {"in": ["landsat-8", "landsat-9"]}}
    items = search_items(cat, "landsat-c2-l2", grid.bbox_wgs, ranges or _season_ranges(cfg), cc)
    if not items:
        label = "rolling latest window" if latest else "configured pre-monsoon seasons"
        raise RuntimeError(f"No Landsat scenes found for the {label}")
    ds = odc.stac.load(items, bands=["lwir11", "qa_pixel"], geobox=grid.geobox(),
                       groupby="solar_day", resampling="nearest", chunks={"x": 1024, "y": 1024})
    dn = ds["lwir11"].astype("float32")
    qa = ds["qa_pixel"].astype("uint16")
    clear = ((qa & 0b11111) == 0) & (dn > 0)
    lst_c = dn * LANDSAT_SCALE + LANDSAT_OFFSET - 273.15
    lst_c = lst_c.where(clear)
    nobs = clear.sum("time")
    med = lst_c.median("time", skipna=True).compute().values
    nobs = nobs.compute().values
    med = np.where(nobs >= min_obs, med, np.nan)
    mean, _ = grid.zonal_mean(med)
    n_mean, _ = grid.zonal_mean(nobs.astype(float))
    dates, first, last = _observation_dates(ds)
    valid_cells_pct = round(float(np.isfinite(mean).mean() * 100.0), 2)
    mean_clear_observations = round(float(np.nanmean(n_mean)), 3) if np.isfinite(n_mean).any() else 0.0
    return {"lst_c": mean, "lst_nobs": n_mean, "scenes": len(items), "days": len(dates),
            "first": first, "last": last, "valid_cells_pct": valid_cells_pct,
            "mean_clear_observations_per_cell": mean_clear_observations}


def sentinel_ndvi(cfg: dict, grid: StudyGrid, cat=None, ranges=None, latest=False) -> dict:
    """Cloud-masked Sentinel-2 NDVI median over pre-monsoon or caller-supplied date ranges."""
    import odc.stac
    cat = cat or open_catalog(cfg)
    cloud_limit = cfg["satellite"].get("latest_cloud_cover_max", 70) if latest else cfg["satellite"]["cloud_cover_max"]
    min_obs = cfg["satellite"].get("latest_min_clear_obs", 1) if latest else cfg["satellite"]["min_clear_obs"]
    items = search_items(cat, "sentinel-2-l2a", grid.bbox_wgs, ranges or _season_ranges(cfg),
                         {"eo:cloud_cover": {"lt": cloud_limit}})

    # Sentinel L2A reflectance offset of -1000 applies from processing baseline 04.00 (January 2022) onward.
    def baseline_ok(it):
        try:
            return float(str(it.properties.get("s2:processing_baseline", "0")).replace("N", "")) >= 4.0
        except (TypeError, ValueError):
            return False
    items = [it for it in items if baseline_ok(it)]
    if not items:
        label = "rolling latest window" if latest else "configured pre-monsoon seasons"
        raise RuntimeError(f"No Sentinel-2 L2A scenes (baseline >= 04.00) found for the {label}")
    ds = odc.stac.load(items, bands=["B04", "B08", "SCL"], geobox=grid.geobox(), groupby="solar_day",
                       resampling={"B04": "average", "B08": "average", "SCL": "nearest"},
                       chunks={"x": 1024, "y": 1024})
    red = ((ds["B04"].astype("float32") - 1000.0) / 10000.0).clip(min=0)
    nir = ((ds["B08"].astype("float32") - 1000.0) / 10000.0).clip(min=0)
    clear = ds["SCL"].isin([4, 5, 6, 7]) & (ds["B04"] > 0) & (ds["B08"] > 0)
    ndvi = ((nir - red) / (nir + red)).where(clear & ((nir + red) > 0))
    nobs = clear.sum("time")
    med = ndvi.median("time", skipna=True).compute().values
    nobs = nobs.compute().values
    med = np.where(nobs >= min_obs, med, np.nan)
    mean, _ = grid.zonal_mean(med)
    n_mean, _ = grid.zonal_mean(nobs.astype(float))
    dates, first, last = _observation_dates(ds)
    valid_cells_pct = round(float(np.isfinite(mean).mean() * 100.0), 2)
    mean_clear_observations = round(float(np.nanmean(n_mean)), 3) if np.isfinite(n_mean).any() else 0.0
    return {"ndvi": mean, "ndvi_nobs": n_mean, "scenes": len(items), "days": len(dates),
            "first": first, "last": last, "valid_cells_pct": valid_cells_pct,
            "mean_clear_observations_per_cell": mean_clear_observations}
