"""Assemble the per-cell baseline table and the city summary. Pure functions, covered by tests."""
from __future__ import annotations
import numpy as np
import pandas as pd
from scipy.spatial import cKDTree
from h3.api import basic_int as h3i
from .grid import StudyGrid
from . import osm_green


def cell_table(grid: StudyGrid, layers: dict[str, np.ndarray]) -> pd.DataFrame:
    lat, lng = grid.centroids()
    area = np.array([h3i.cell_area(int(c), unit="km^2") for c in grid.cells])
    df = pd.DataFrame({"h3": grid.hex_ids(), "lat": lat.round(6), "lng": lng.round(6), "area_km2": area.round(5)})
    for k, v in layers.items():
        df[k] = np.asarray(v, dtype="float64")
    if "tree_count" in df:
        df["tree_density_ha"] = df["tree_count"] / (df["area_km2"] * 100.0)
    need = {"bare_pct", "grass_pct", "shrub_pct", "park_ha", "forest_ha"}
    if need <= set(df.columns):
        # open land estimate: bare + grass + shrub cover, minus what OSM already maps as park or forest (avoid double counting)
        open_ha = (df["bare_pct"] + df["grass_pct"] + df["shrub_pct"]) / 100.0 * df["area_km2"] * 100.0 - df["park_ha"] - df["forest_ha"]
        df["open_land_ha"] = open_ha.clip(lower=0)
    if "pop" in df and "pop_access" in df:
        with np.errstate(invalid="ignore", divide="ignore"):
            df["access_share"] = np.where(df["pop"] > 0, df["pop_access"] / df["pop"], np.nan)
    return df


def access_from_population(pop: dict, polys_public_qualifying: list, distance_m: float, n_cells: int) -> dict:
    d = osm_green.nearest_distance_m(pop["xy"], polys_public_qualifying)
    served = d <= distance_m
    pop_access = np.bincount(pop["cell_idx"], weights=pop["people"] * served, minlength=n_cells)
    return {"pop_access": pop_access, "pixel_distance_m": d}


def unserved_within(pop_xy: np.ndarray, people: np.ndarray, pixel_distance_m: np.ndarray, access_m: float,
                    centroids_xy: np.ndarray, radius_m: float) -> np.ndarray:
    """People within `radius_m` of each point who are NOT already within `access_m` of a qualifying park."""
    unserved = pixel_distance_m > access_m
    if not unserved.any():
        return np.zeros(len(centroids_xy))
    w = people[unserved]
    tree = cKDTree(pop_xy[unserved])
    hits = tree.query_ball_point(centroids_xy, r=radius_m)
    return np.array([w[h].sum() if len(h) else 0.0 for h in hits])


def _nan_pct(a: np.ndarray, q: float):
    a = a[np.isfinite(a)]
    return float(np.percentile(a, q)) if a.size else None


def city_summary(df: pd.DataFrame, extra: dict | None = None) -> dict:
    s: dict = {"n_cells": int(len(df)), "area_km2": round(float(df["area_km2"].sum()), 1)}
    if "tree_count" in df:
        s["trees_total"] = int(df["tree_count"].sum())
        s["trees_per_ha"] = round(float(df["tree_count"].sum() / (df["area_km2"].sum() * 100.0)), 2)
        s["cells_without_trees_pct"] = round(float((df["tree_count"] == 0).mean() * 100), 1)
    if "ndvi" in df:
        s["ndvi_median"] = _round(_nan_pct(df["ndvi"].to_numpy(), 50), 3)
    if "lst_c" in df:
        v = df["lst_c"].to_numpy()
        s.update({"lst_c_median": _round(_nan_pct(v, 50), 1), "lst_c_p10": _round(_nan_pct(v, 10), 1),
                  "lst_c_p90": _round(_nan_pct(v, 90), 1)})
        if "pop" in df and np.isfinite(v).any():
            thr = np.nanpercentile(v, 90)
            hot = df["lst_c"] >= thr
            s["lst_p90_threshold_c"] = round(float(thr), 1)
            s["pop_in_hottest_decile_cells"] = int(round(float(df.loc[hot, "pop"].sum())))
    for c in ("builtup_pct", "treecover_pct", "grass_pct", "water_pct"):
        if c in df:
            w = df["area_km2"].to_numpy()
            m = np.isfinite(df[c].to_numpy())
            s[c.replace("_pct", "_share_pct")] = _round(float(np.average(df[c].to_numpy()[m], weights=w[m])) if m.any() else None, 1)
    if "pop" in df:
        s["pop_total"] = int(round(float(df["pop"].sum())))
    if "pop_access" in df:
        s["pop_with_park_access"] = int(round(float(df["pop_access"].sum())))
        tot = float(df["pop"].sum())
        s["pop_without_park_access"] = int(round(tot - float(df["pop_access"].sum())))
        s["pop_without_park_access_pct"] = round(100.0 * (tot - float(df["pop_access"].sum())) / tot, 1) if tot > 0 else None
    if "park_ha" in df:
        s["public_green_mapped_ha_in_study_area"] = round(float(df["park_ha"].sum()), 1)
    if "forest_ha" in df:
        s["forest_reserve_mapped_ha_in_study_area"] = round(float(df["forest_ha"].sum()), 1)
    if extra:
        s.update(extra)
    return s


def _round(x, n):
    return None if x is None else round(float(x), n)
