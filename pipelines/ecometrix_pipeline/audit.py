"""Milestone M0: the pilot-city audit. Every value is measured by the pipeline during the build."""
from __future__ import annotations


def _check(cid: str, title: str, status: str, rule: str, evidence: dict, note: str = "") -> dict:
    return {"id": cid, "title": title, "status": status, "rule": rule, "evidence": evidence, "note": note}


def build_audit(cfg: dict, ctx: dict) -> dict:
    checks = []
    tc_cfg = cfg["tree_census"]
    b = ctx.get("boundary")
    if b:
        ok = not b["fallback"]
        checks.append(_check("boundary", "City boundary", "pass" if ok else "warn",
                             "The 2025 PMC electoral-ward boundary or an OSM administrative boundary is obtained and passes area/geometry sanity checks.",
                             {"source": b["source"], "area_km2": b["area_km2"], "osm_ref": b.get("osm_ref"),
                              "boundary_dataset": b.get("boundary_dataset"),
                              "boundary_dataset_url": b.get("boundary_dataset_url"),
                              "boundary_resource_name": b.get("boundary_resource_name"),
                              "boundary_resource_credit": b.get("boundary_resource_credit"),
                              "boundary_metadata_modified": b.get("boundary_metadata_modified"),
                              "boundary_resource_modified": b.get("boundary_resource_modified"),
                              "boundary_ward_features": b.get("boundary_ward_features"),
                              "h3_cells": ctx.get("n_cells")},
                             "; ".join(b.get("notes", [])) or ("Boundary polygon accepted." if ok else
                              "Boundary lookup failed; a configured bounding box is used instead.")))
    t = ctx.get("trees")
    if t:
        valid = t["rows_valid_coords"] / t["rows_total"] if t["rows_total"] else 0
        recon = {"rows_loaded": t["rows_total"], "valid_coordinates_pct": round(100 * valid, 2),
                 "rows_inside_study_area": t["rows_inside_study_area"], "parts_read": t["n_parts_read"],
                 "published_claim": tc_cfg["published_total_claim"], "listed_parts_total": tc_cfg["listed_parts_total"],
                 "coordinate_detection": t["coordinate_detection"]}
        status = "pass" if valid >= 0.90 else "fail"
        checks.append(_check("trees", "Tree census loads and is clean", status,
                             "At least 90% of rows have valid coordinates; the loaded count is reconciled with published figures.",
                             recon, "The explainer quotes 4.09 million trees, but the listed parts add up to about 4.009 million. "
                                    "The loaded row count above is what the pipeline actually read."))
    # Recent satellite acquisitions are separate from the stable pre-monsoon model inputs.
    latest = ctx.get("latest_satellite") or {}
    latest_max_age = int(cfg.get("satellite", {}).get("latest_max_age_days", 45))
    latest_min_coverage = float(cfg.get("satellite", {}).get("latest_min_valid_cells_pct", 50.0))
    latest_evidence = {}
    latest_ok = True
    for key, label in (("landsat", "Landsat 8/9 LST"), ("sentinel2", "Sentinel-2 NDVI")):
        record = latest.get(key)
        if record:
            latest_evidence[key] = {"title": label, **record}
            age_ok = (isinstance(record.get("age_days"), int)
                      and 0 <= record["age_days"] <= latest_max_age)
            coverage_ok = (isinstance(record.get("valid_cells_pct"), (int, float))
                           and record["valid_cells_pct"] >= latest_min_coverage)
            latest_ok = latest_ok and age_ok and coverage_ok
        else:
            latest_evidence[key] = {"title": label, "available": False}
            latest_ok = False
    checks.append(_check(
        "latest_satellite", "Latest satellite observations", "pass" if latest_ok else "warn",
        f"Both rolling-window composites must be no older than {latest_max_age} days and cover at least {latest_min_coverage}% of study-area cells.",
        latest_evidence,
        "These are the newest cloud-filtered acquisitions available in the provider catalogue, composited over a rolling window; this is near-real-time monitoring, not a live sensor feed. "
        "Cloud masking can leave some cells without a value. Pre-monsoon baseline composites remain separate for seasonal consistency."
    ))

    sc = ctx.get("scene_counts")
    if sc:
        ok_ls = sum(1 for v in sc["landsat"].values() if v >= 3)
        ok_s2 = sum(1 for v in sc["sentinel2"].values() if v >= 3)
        status = "pass" if (ok_ls >= 5 and ok_s2 >= 5) else "warn"
        checks.append(_check("satellite", "Satellite coverage (pre-monsoon)", status,
                             "At least 3 cloud-filtered scenes per year for 5 or more years, for Landsat 8/9 and Sentinel-2.",
                             {"landsat_scenes_per_year": sc["landsat"], "sentinel2_scenes_per_year": sc["sentinel2"],
                              "years_ok_landsat": ok_ls, "years_ok_sentinel2": ok_s2}))
    p = ctx.get("population")
    if p:
        ps = ctx.get("popseries")
        yrs = len(ps["years"]) if ps else 0
        status = "pass" if yrs >= 15 else "warn"
        ev = {"baseline_dataset": "WorldPop constrained 2020 (100 m)", "people_in_study_area": int(round(p["total"])),
              "pixels": p["pixels"], "read_method": p["how"], "yearly_series_years_read": yrs}
        if ps and ps["missing"]:
            ev["yearly_series_years_missing"] = sorted(ps["missing"])
        checks.append(_check("population", "Gridded population over time", status,
                             "A yearly series over about two decades plus an official census anchor.", ev,
                             "The yearly series is WorldPop's modelled product, not a census count. An official census anchor is still to be added; "
                             "until then the forecast is labelled MODELLED."))
    o = ctx.get("osm")
    if o:
        status = "pass" if o["public_green_qualifying_polygons"] >= 20 else "warn"
        checks.append(_check("parks", "Existing parks and open space", status,
                             "Enough mapped public green space to compute who already has access.", o,
                             "OpenStreetMap is crowd-sourced. Compare against the municipality's own park list before relying on it for decisions."))
    checks.append(_check("costs", "Cost benchmarks", "manual",
                         "At least 3 usable cost sources for parks or tree planting.", {},
                         "Cannot be automated. Person B collects these from municipal budgets, state rate schedules and published studies (Appendix A of the roadmap)."))
    return {"generated_at": ctx.get("generated_at"), "checks": checks}
