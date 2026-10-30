"""M5: candidate sites. A site is a plantable patch of OPEN LAND inside one hexagon, estimated from satellite land cover
(bare + grass + shrub, minus what OpenStreetMap already maps as park or forest). It is NOT a surveyed parcel:
every site is flagged "needs field verification", and ownership, legality and soil are unknown.

Two intervention types, because each has a local, sourced basis:
  pocket_park   greenness target = typical NDVI of the selected city's mapped public parks (data-derived)
  mini_forest   greenness target = typical NDVI of the selected city's mapped forest (data-derived); dense native planting
Street-tree corridors and green roofs are not included yet: they need road-side tree counts and rooftop data that are not built.
"""
from __future__ import annotations
import numpy as np
import pandas as pd
import heat_model as hm

TYPES = ["pocket_park", "mini_forest"]


def build(cells: pd.DataFrame, need_df: pd.DataFrame, heat: dict | None, targets: dict, cand_cfg: dict) -> pd.DataFrame:
    need_cols = {"open_land_ha", "pop", "ndvi", "lat", "lng", "area_km2", "h3"}
    missing = sorted(need_cols - set(cells.columns))
    if missing:
        raise ValueError(f"cannot generate sites without {missing}")
    base = cells.merge(need_df, on="h3", how="left")
    cell_ha = base["area_km2"] * 100.0
    models = None
    if heat and heat.get("status") == "ok":
        models = hm.bootstrap_models(heat["chosen"], heat["_d"], n=40)
    frames = []
    for t in TYPES:
        cfg = cand_cfg[t]
        m = (base["open_land_ha"] >= cfg["min_site_ha"]) & (base["pop"] > 0)
        sub = base[m].copy()
        if sub.empty:
            continue
        sub["type"] = t
        sub["area_ha"] = np.minimum(sub["open_land_ha"], cfg["max_site_ha"])
        sub["cell_area_ha"] = cell_ha[m]
        sub["ndvi_before"] = sub["ndvi"]
        tg = targets.get(t, {})
        cool = np.full((3, len(sub)), np.nan)
        after = np.full(len(sub), np.nan)
        feas = models is not None and tg.get("available") and {"builtup_pct", "water_pct"} <= set(sub.columns)
        if feas:
            f = (sub["area_ha"] / sub["cell_area_ha"]).to_numpy()
            nb = sub["ndvi"].to_numpy(float)
            after = nb + f * np.maximum(0.0, tg["ndvi_target"] - nb)
            ok = np.isfinite(nb) & sub["builtup_pct"].notna().to_numpy() & sub["water_pct"].notna().to_numpy()
            Xb = np.column_stack([nb, sub["builtup_pct"], sub["water_pct"]])
            Xa = np.column_stack([after, sub["builtup_pct"], sub["water_pct"]])
            if ok.any():
                d = hm.delta_lst(models, Xb[ok], Xa[ok])
                cool[0, ok], cool[1, ok], cool[2, ok] = np.percentile(d, 10, axis=0), np.percentile(d, 50, axis=0), np.percentile(d, 90, axis=0)
        sub["ndvi_after"] = after
        sub["dlst_p10"], sub["dlst_p50"], sub["dlst_p90"] = cool
        frames.append(sub)
    if not frames:
        return pd.DataFrame()
    out = pd.concat(frames, ignore_index=True)
    out["site_id"] = out["h3"] + ":" + out["type"]
    out["verification"] = "candidate: needs field verification"
    keep = ["site_id", "h3", "type", "lat", "lng", "area_ha", "open_land_ha", "cell_area_ha", "pop", "pop_unserved_access", "pop_unserved_300m",
            "ndvi_before", "ndvi_after", "dlst_p10", "dlst_p50", "dlst_p90", "verification"]
    keep += [c for c in out.columns if c.startswith("need_")]
    return out[[c for c in keep if c in out.columns]].reset_index(drop=True)
