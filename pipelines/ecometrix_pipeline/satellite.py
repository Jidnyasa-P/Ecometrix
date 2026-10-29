"""Satellite layers from the Microsoft Planetary Computer STAC API (free, anonymous signed access).

  ESA WorldCover (10 m)   land-cover shares per cell
  Landsat 8/9 C2 L2       land-surface temperature (LST), pre-monsoon median
  Sentinel-2 L2A          NDVI, pre-monsoon median

Landsat and Sentinel-2 are cloud-masked, composited by median over several pre-monsoon seasons.
LST is a mid-morning snapshot of SURFACE temperature, not air temperature.
"""
from __future__ import annotations
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


def search_items(cat, collection: str, bbox, ranges, extra_query=None) -> list:
    seen, items = set(), []
    for rng in ranges:
        s = cat.search(collections=[collection], bbox=list(bbox), datetime=rng, query=extra_query or {})
        for it in s.items():
            if it.id not in seen:
                seen.add(it.id); items.append(it)
    return items


def scene_counts(cfg: dict, grid: StudyGrid, cat=None) -> dict:
    """Usable (cloud-filtered) pre-monsoon scene counts per year: the audit's satellite-coverage check."""
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


def landsat_lst(cfg: dict, grid: StudyGrid, cat=None) -> dict:
    import odc.stac
    cat = cat or open_catalog(cfg)
    cc = {"eo:cloud_cover": {"lt": cfg["satellite"]["cloud_cover_max"]},
          "platform": {"in": ["landsat-8", "landsat-9"]}}
    items = search_items(cat, "landsat-c2-l2", grid.bbox_wgs, _season_ranges(cfg), cc)
    if not items:
        raise RuntimeError("No Landsat scenes found for the configured seasons")
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
    med = np.where(nobs >= cfg["satellite"]["min_clear_obs"], med, np.nan)
    mean, cnt = grid.zonal_mean(med)
    n_mean, _ = grid.zonal_mean(nobs.astype(float))
    dates = sorted({str(t)[:10] for t in ds["time"].values})
    return {"lst_c": mean, "lst_nobs": n_mean, "scenes": len(items), "days": len(dates),
            "first": dates[0], "last": dates[-1]}


def sentinel_ndvi(cfg: dict, grid: StudyGrid, cat=None) -> dict:
    import odc.stac
    cat = cat or open_catalog(cfg)
    items = search_items(cat, "sentinel-2-l2a", grid.bbox_wgs, _season_ranges(cfg),
                         {"eo:cloud_cover": {"lt": cfg["satellite"]["cloud_cover_max"]}})
    # reflectance offset of -1000 applies from processing baseline 04.00 (January 2022) onward
    def baseline_ok(it):
        try:
            return float(str(it.properties.get("s2:processing_baseline", "0")).replace("N", "")) >= 4.0
        except ValueError:
            return False
    items = [it for it in items if baseline_ok(it)]
    if not items:
        raise RuntimeError("No Sentinel-2 L2A scenes (baseline >= 04.00) found for the configured seasons")
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
    med = np.where(nobs >= cfg["satellite"]["min_clear_obs"], med, np.nan)
    mean, _ = grid.zonal_mean(med)
    dates = sorted({str(t)[:10] for t in ds["time"].values})
    return {"ndvi": mean, "scenes": len(items), "days": len(dates), "first": dates[0], "last": dates[-1]}
