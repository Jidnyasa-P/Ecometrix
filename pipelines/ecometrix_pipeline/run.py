"""Build the real baseline for the pilot city.

    python -m ecometrix_pipeline.run                # everything
    python -m ecometrix_pipeline.run --skip landsat # skip a layer
    python -m ecometrix_pipeline.run --only osm,trees

Every layer is independent. If one source fails, the others still build and the failure is recorded
in manifest.json and shown honestly in the app. Nothing is ever filled in with placeholder values.
"""
from __future__ import annotations
import argparse
import json
import os
import traceback
from datetime import date, datetime, timezone
from pathlib import Path
import numpy as np
import pandas as pd
from . import __version__
from .config import load_config, REPO_ROOT
from .http import session
from .boundary import fetch_boundary
from .grid import build_grid
from . import tree_census, osm_green, population, satellite, metrics, audit

LAYER_META = {
    "trees": {"title": "Pune Tree Census 2019", "evidence": "MEASURED", "license": "Public domain (PMC open data via OpenCity)",
              "source": "https://data.opencity.in/dataset/pune-tree-census-2019"},
    "osm": {"title": "Mapped green space (OpenStreetMap)", "evidence": "MEASURED", "license": "ODbL, © OpenStreetMap contributors",
            "source": "https://www.openstreetmap.org (Overpass API)"},
    "worldcover": {"title": "Land cover (ESA WorldCover)", "evidence": "MODELLED", "license": "CC BY 4.0, ESA WorldCover",
                   "source": "https://planetarycomputer.microsoft.com/dataset/esa-worldcover"},
    "landsat": {"title": "Land-surface temperature (Landsat 8/9)", "evidence": "MEASURED", "license": "Public domain (USGS/NASA)",
                "source": "https://planetarycomputer.microsoft.com/dataset/landsat-c2-l2"},
    "sentinel": {"title": "Vegetation index NDVI (Sentinel-2 pre-monsoon baseline)", "evidence": "MEASURED", "license": "Copernicus Sentinel data, free and open",
                 "source": "https://planetarycomputer.microsoft.com/dataset/sentinel-2-l2a"},
    "landsat_latest": {"title": "Latest surface temperature (Landsat 8/9)", "evidence": "MEASURED", "license": "Public domain (USGS/NASA)",
                       "source": "https://planetarycomputer.microsoft.com/dataset/landsat-c2-l2"},
    "sentinel_latest": {"title": "Latest greenness NDVI (Sentinel-2)", "evidence": "MEASURED", "license": "Copernicus Sentinel data, free and open",
                        "source": "https://planetarycomputer.microsoft.com/dataset/sentinel-2-l2a"},
    "popseries": {"title": "Population history 2000-2020 (WorldPop yearly)", "evidence": "MODELLED", "license": "CC BY 4.0, WorldPop",
                  "source": "https://data.worldpop.org/GIS/Population/Global_2000_2020/2020/IND"},
    "population": {"title": "Population (WorldPop 2020, constrained)", "evidence": "MODELLED", "license": "CC BY 4.0, WorldPop",
                   "source": "https://hub.worldpop.org/geodata/summary?id=49804"},
}


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default=None)
    ap.add_argument("--out", default=str(REPO_ROOT / "data" / "outputs"))
    ap.add_argument("--only", default="")
    ap.add_argument("--skip", default="")
    ap.add_argument("--workdir", default=str(REPO_ROOT / "data" / "raw"))
    args = ap.parse_args(argv)
    cfg = load_config(args.config)
    out = Path(args.out); out.mkdir(parents=True, exist_ok=True)
    only = {x for x in args.only.split(",") if x}
    skip = {x for x in args.skip.split(",") if x}
    want = lambda n: (not only or n in only) and n not in skip
    sess = session()
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    layers_status: dict[str, dict] = {}
    ctx: dict = {"generated_at": now}

    def run_step(name, fn):
        meta = dict(LAYER_META.get(name, {}))
        if not want(name):
            layers_status[name] = {**meta, "status": "skipped"}
            return None
        try:
            res = fn()
            layers_status[name] = {**meta, "status": "ok"}
            return res
        except Exception as e:
            traceback.print_exc()
            layers_status[name] = {**meta, "status": "failed", "reason": f"{type(e).__name__}: {e}"}
            return None

    print("1/7 boundary")
    b = fetch_boundary(cfg, sess)
    ctx["boundary"] = {k: v for k, v in b.items() if k != "geometry"}
    grid = build_grid(b["geometry"], cfg["h3_resolution"], cfg["utm_epsg"], cfg["pixel_m"])
    ctx["n_cells"] = grid.n_cells
    print(f"   {grid.n_cells} cells, {b['source']}, {b['area_km2']} km2")

    cols: dict[str, np.ndarray] = {}
    summary_extra: dict = {}
    vintages: dict = {}

    print("2/7 tree census")
    def _trees():
        t = tree_census.count_trees(cfg, grid, sess, Path(args.workdir) / "trees")
        ctx["trees"] = t
        cols["tree_count"] = t["per_cell"]
        summary_extra["trees_rows_loaded"] = t["rows_total"]
        summary_extra["trees_species_top"] = t["species_top"]
        summary_extra["trees_species_distinct"] = t["species_distinct"]
        vintages["trees"] = {"vintage": "August 2019", "rows": t["rows_total"], "coordinates": t["coordinate_detection"]}
    run_step("trees", _trees)

    print("3/7 OpenStreetMap green space")
    polys = {}
    def _osm():
        data = osm_green.fetch_overpass(cfg, grid.bbox_wgs, sess)
        nonlocal polys
        polys = osm_green.parse_overpass(data, cfg["utm_epsg"])
        ctx["osm"] = osm_green.summarize(polys, cfg["access"]["min_area_ha"])
        qual = [p for p in polys["public_green"] if p.area / 1e4 >= cfg["access"]["min_area_ha"]]
        polys["qualifying"] = qual
        lat, lng = grid.centroids()
        cx, cy = grid.to_utm.transform(lng, lat)
        cols["dist_park_m"] = np.minimum(osm_green.nearest_distance_m(np.column_stack([cx, cy]), qual), 99999.0)
        cols["park_ha"] = osm_green.area_per_cell_ha(grid, polys["public_green"])
        cols["forest_ha"] = osm_green.area_per_cell_ha(grid, polys["forest_reserve"])
        vintages["osm"] = {"vintage": f"queried {now[:10]}", **ctx["osm"]}
    run_step("osm", _osm)

    print("4/7 land cover, 5/7 LST, 6/7 NDVI")
    need_sat = any(want(n) for n in ("worldcover", "landsat", "sentinel", "landsat_latest", "sentinel_latest"))
    cat = None
    if need_sat:
        try:
            cat = satellite.open_catalog(cfg)
        except Exception as e:
            for n in ("worldcover", "landsat", "sentinel", "landsat_latest", "sentinel_latest"):
                layers_status[n] = {**LAYER_META[n], "status": "failed", "reason": f"STAC catalog unavailable: {e!r}"}
    def _wc():
        r = satellite.worldcover(cfg, grid, cat); cols.update(r["layers"])
        vintages["worldcover"] = {"vintage": f"{r['version']} ({', '.join(map(str, r['years']))})", "tiles": r["items"]}
    def _ls():
        r = satellite.landsat_lst(cfg, grid, cat); cols["lst_c"] = r["lst_c"]; cols["lst_nobs"] = r["lst_nobs"]
        vintages["landsat"] = {"vintage": f"pre-monsoon {r['first']} to {r['last']}", "scenes": r["scenes"], "clear_days": r["days"]}
    def _s2():
        r = satellite.sentinel_ndvi(cfg, grid, cat); cols["ndvi"] = r["ndvi"]
        vintages["sentinel"] = {"vintage": f"pre-monsoon {r['first']} to {r['last']}", "scenes": r["scenes"], "clear_days": r["days"]}
    def _latest_meta(r):
        observation_date = date.fromisoformat(r["last"])
        age = (datetime.now(timezone.utc).date() - observation_date).days
        return {"first_observation": r["first"], "last_observation": r["last"], "age_days": age,
                "scenes": r["scenes"], "clear_days": r["days"],
                "valid_cells_pct": r["valid_cells_pct"],
                "mean_clear_observations_per_cell": r["mean_clear_observations_per_cell"],
                "window_days": int(cfg["satellite"].get("latest_window_days", 180))}
    def _ls_latest():
        ranges = satellite.latest_ranges(cfg)
        r = satellite.landsat_lst(cfg, grid, cat, ranges=ranges, latest=True)
        cols["lst_latest_c"] = r["lst_c"]
        cols["lst_latest_nobs"] = r["lst_nobs"]
        detail = _latest_meta(r)
        vintages["landsat_latest"] = {"vintage": f"latest available; rolling window {ranges[0]}", **detail}
        ctx.setdefault("latest_satellite", {})["landsat"] = detail
    def _s2_latest():
        ranges = satellite.latest_ranges(cfg)
        r = satellite.sentinel_ndvi(cfg, grid, cat, ranges=ranges, latest=True)
        cols["ndvi_latest"] = r["ndvi"]
        cols["ndvi_latest_nobs"] = r["ndvi_nobs"]
        detail = _latest_meta(r)
        vintages["sentinel_latest"] = {"vintage": f"latest available; rolling window {ranges[0]}", **detail}
        ctx.setdefault("latest_satellite", {})["sentinel2"] = detail
    if cat is not None:
        run_step("worldcover", _wc); run_step("landsat", _ls); run_step("sentinel", _s2)
        run_step("landsat_latest", _ls_latest); run_step("sentinel_latest", _s2_latest)
        if any(want(n) for n in ("worldcover", "landsat", "sentinel", "landsat_latest", "sentinel_latest")):
            try:
                ctx["scene_counts"] = satellite.scene_counts(cfg, grid, cat)
            except Exception as e:
                ctx["scene_counts_error"] = repr(e)

    print("7/7 population and access")
    def _pop():
        p = population.load_population(cfg, grid, sess)
        ctx["population"] = p
        cols["pop"] = p["per_cell"]
        vintages["population"] = {"vintage": f"{cfg['population']['year']}", "read": p["how"], "pixels": p["pixels"]}
        if polys.get("qualifying") is not None:
            acc = metrics.access_from_population(p, polys["qualifying"], cfg["access"]["distance_m"], grid.n_cells)
            cols["pop_access"] = acc["pop_access"]
            lat, lng = grid.centroids()
            cx, cy = grid.to_utm.transform(lng, lat)
            cxy = np.column_stack([cx, cy])
            cols["pop_unserved_300m"] = metrics.unserved_within(p["xy"], p["people"], acc["pixel_distance_m"],
                                                                cfg["access"]["distance_m"], cxy, cfg["access"]["distance_m"])
            ci, pi = metrics.unserved_pairs(p["xy"], p["people"], acc["pixel_distance_m"], cfg["access"]["distance_m"], cxy,
                                            cfg["access"]["distance_m"])
            hexes = np.array(grid.hex_ids())
            pd.DataFrame({"h3": hexes[ci], "pixel": pi.astype("int64"), "people": p["people"][pi]}).to_parquet(out / "site_pixels.parquet", index=False)
    run_step("population", _pop)

    def _popseries():
        r = population.load_series(cfg, grid, sess=sess)
        if len(r["per_cell_by_year"]) < 5:
            raise RuntimeError(f"only {len(r['per_cell_by_year'])} yearly rasters could be read; first errors: {list(r['missing'].items())[:2]}")
        ps = pd.DataFrame({"h3": grid.hex_ids()})
        for y, v in sorted(r["per_cell_by_year"].items()):
            ps[f"y{y}"] = v
        ps.to_parquet(out / "popseries.parquet", index=False)
        ctx["popseries"] = {"years": sorted(r["per_cell_by_year"]), "missing": r["missing"]}
        vintages["popseries"] = {"vintage": f"{min(r['per_cell_by_year'])} to {max(r['per_cell_by_year'])}",
                                 "years_read": len(r["per_cell_by_year"]), "years_missing": len(r["missing"])}
    run_step("popseries", _popseries)

    df = metrics.cell_table(grid, cols)
    df.to_parquet(out / "cells.parquet", index=False)
    summary = metrics.city_summary(df, summary_extra)
    summary.update({"city": cfg["city"], "h3_resolution": cfg["h3_resolution"],
                    "access_rule": f">= {cfg['access']['min_area_ha']} ha public green within {cfg['access']['distance_m']} m (WHO)"})
    dump_json(out / "summary.json", summary)
    dump_json(out / "audit.json", audit.build_audit(cfg, ctx))
    for k, v in vintages.items():
        layers_status.setdefault(k, {})["detail"] = v
    manifest = {"pipeline_version": __version__, "generated_at": now, "git_sha": os.environ.get("GITHUB_SHA"),
                "city": cfg["city"], "h3_resolution": cfg["h3_resolution"], "pixel_m": cfg["pixel_m"],
                "boundary": ctx["boundary"], "n_cells": grid.n_cells, "columns": list(df.columns),
                "layers": layers_status}
    dump_json(out / "manifest.json", manifest)
    failed = [k for k, v in layers_status.items() if v.get("status") == "failed"]
    quality_warnings = []
    if b.get("fallback"):
        quality_warnings.append("Study-area boundary is a configured bounding-box fallback.")
    max_age = int(cfg.get("satellite", {}).get("latest_max_age_days", 45))
    min_coverage = float(cfg.get("satellite", {}).get("latest_min_valid_cells_pct", 50.0))
    for layer_name, key in (("landsat_latest", "landsat"), ("sentinel_latest", "sentinel2")):
        if not want(layer_name):
            continue
        detail = ctx.get("latest_satellite", {}).get(key)
        if not detail:
            quality_warnings.append(f"{layer_name} has no latest-observation metadata.")
            continue
        if detail["age_days"] < 0 or detail["age_days"] > max_age:
            quality_warnings.append(f"{layer_name} newest observation age is {detail['age_days']} days (allowed range 0-{max_age}).")
        if detail["valid_cells_pct"] < min_coverage:
            quality_warnings.append(f"{layer_name} covers only {detail['valid_cells_pct']}% of cells (limit {min_coverage}%).")
    if quality_warnings:
        print("data-quality warnings:", quality_warnings)
    print("done. layers:", {k: v["status"] for k, v in layers_status.items()})
    return 1 if (failed or quality_warnings) and not os.environ.get("ECOMETRIX_ALLOW_PARTIAL") else 0


def _clean(o):
    if isinstance(o, dict): return {str(k): _clean(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)): return [_clean(v) for v in o]
    if isinstance(o, np.ndarray): return _clean(o.tolist())
    if isinstance(o, (np.integer,)): return int(o)
    if isinstance(o, (np.floating, float)): return float(o) if np.isfinite(o) else None
    return o


def dump_json(path, obj):
    Path(path).write_text(json.dumps(_clean(obj), indent=2, allow_nan=False), encoding="utf-8")


def _nan_safe(o):
    if isinstance(o, (np.integer,)): return int(o)
    if isinstance(o, (np.floating,)): return None if not np.isfinite(o) else float(o)
    if isinstance(o, np.ndarray): return o.tolist()
    raise TypeError(type(o))


if __name__ == "__main__":
    raise SystemExit(main())
