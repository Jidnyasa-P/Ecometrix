"""Tests use small synthetic inputs built here in the test. They exist only to verify the code paths;
nothing in this file is ever shipped as application data."""
import json
import numpy as np
import pandas as pd
import pytest
import rasterio
from rasterio.transform import from_origin
from shapely.geometry import box, Polygon
from h3.api import basic_int as h3i

from ecometrix_pipeline import grid as G, tree_census, osm_green, population, metrics, audit, boundary, run
from ecometrix_pipeline.config import load_config

CFG = load_config()
# a ~2.2 km square near the centre of Pune
BOX = box(73.84, 18.50, 73.86, 18.52)


@pytest.fixture(scope="module")
def grid():
    return G.build_grid(BOX, 9, 32643, 30)


def test_grid_cells_and_pixels(grid):
    assert grid.n_cells > 20
    h, w = grid.shape
    assert grid.pixel_cell_idx.shape == (h, w)
    # every mapped pixel's cell must really contain that pixel centre
    for (r, c) in [(h // 2, w // 2), (h // 3, w // 3), (h // 2, w // 4)]:
        idx = grid.pixel_cell_idx[r, c]
        if idx < 0:
            continue
        x = grid.transform.c + (c + 0.5) * grid.pixel_m
        y = grid.transform.f - (r + 0.5) * grid.pixel_m
        lng, lat = grid.to_wgs.transform(x, y)
        assert h3i.latlng_to_cell(lat, lng, 9) == int(grid.cells[idx])


def test_zonal_mean_constant(grid):
    arr = np.full(grid.shape, 7.0)
    mean, cnt = grid.zonal_mean(arr)
    m = cnt > 0
    assert np.allclose(mean[m], 7.0)
    assert cnt.sum() == (grid.pixel_cell_idx >= 0).sum()


def test_zonal_mean_respects_nan_and_valid(grid):
    arr = np.ones(grid.shape)
    arr[::2] = np.nan
    mean, cnt = grid.zonal_mean(arr)
    assert np.nanmax(mean) == 1.0
    valid = np.zeros(grid.shape, bool)
    _, cnt2 = grid.zonal_mean(np.ones(grid.shape), valid=valid)
    assert cnt2.sum() == 0


def _write_trees(path, rows, mode):
    if mode == "cols":
        pd.DataFrame({"id": range(len(rows)), "botanical_name": ["A"] * len(rows),
                      "latitude": [r[0] for r in rows], "longitude": [r[1] for r in rows]}).to_csv(path, index=False)
    else:
        pd.DataFrame({"id": range(len(rows)), "geo_location": [f"{r[0]}, {r[1]}" for r in rows]}).to_csv(path, index=False)


def test_tree_census_counts_both_formats(tmp_path, grid):
    inside = [(18.51, 73.85)] * 5 + [(18.505, 73.845)] * 2
    outside = [(19.5, 73.85), (18.51, 70.0)]          # far away: rejected by the plausibility guard
    broken = [(np.nan, np.nan)]
    f1, f2 = tmp_path / "a.csv", tmp_path / "b.csv"
    _write_trees(f1, inside + outside + broken, "cols")
    _write_trees(f2, inside, "geo")
    res = tree_census.count_trees(CFG, grid, None, files=[f1, f2])
    assert res["rows_total"] == len(inside) * 2 + len(outside) + len(broken)
    assert res["rows_valid_coords"] == len(inside) * 2
    assert res["per_cell"].sum() == len(inside) * 2
    assert any("combined" in d for d in res["coordinate_detection"])
    assert res["species_top"][0]["species"] == "A"


def test_tree_census_swapped_combined_column(tmp_path, grid):
    f = tmp_path / "s.csv"
    pd.DataFrame({"geo_location": ["73.85, 18.51"] * 3}).to_csv(f, index=False)   # lon, lat order
    res = tree_census.count_trees(CFG, grid, None, files=[f])
    assert res["rows_valid_coords"] == 3 and "lon,lat" in res["coordinate_detection"][0]


def _overpass_json():
    def ring(w, s, e, n):
        return [{"lat": s, "lon": w}, {"lat": s, "lon": e}, {"lat": n, "lon": e}, {"lat": n, "lon": w}, {"lat": s, "lon": w}]
    return {"elements": [
        {"type": "way", "id": 1, "tags": {"leisure": "park"}, "geometry": ring(73.845, 18.505, 73.847, 18.507)},       # ~4.6 ha public
        {"type": "way", "id": 2, "tags": {"leisure": "garden"}, "geometry": ring(73.855, 18.515, 73.8553, 18.5153)},  # ~0.1 ha: too small
        {"type": "way", "id": 3, "tags": {"leisure": "park", "access": "private"}, "geometry": ring(73.85, 18.50, 73.851, 18.501)},
        {"type": "way", "id": 4, "tags": {"landuse": "forest"}, "geometry": ring(73.841, 18.511, 73.843, 18.513)},
        {"type": "way", "id": 5, "tags": {"landuse": "grass"}, "geometry": ring(73.858, 18.505, 73.859, 18.506)},
    ]}


def test_osm_classification_and_areas():
    polys = osm_green.parse_overpass(_overpass_json(), 32643)
    assert len(polys["public_green"]) == 2          # private park excluded
    assert len(polys["forest_reserve"]) == 1 and len(polys["open_green"]) == 1
    s = osm_green.summarize(polys, 0.5)
    assert s["public_green_qualifying_polygons"] == 1
    assert 4.0 < s["public_green_qualifying_ha"] < 5.2


def test_nearest_distance_and_area_per_cell(grid):
    polys = osm_green.parse_overpass(_overpass_json(), 32643)
    qual = [p for p in polys["public_green"] if p.area / 1e4 >= 0.5]
    inside_pt = np.array([[qual[0].centroid.x, qual[0].centroid.y]])
    far_pt = np.array([[qual[0].centroid.x + 1000, qual[0].centroid.y]])
    assert osm_green.nearest_distance_m(inside_pt, qual)[0] == 0
    d = osm_green.nearest_distance_m(far_pt, qual)[0]
    assert 700 < d < 1000
    assert np.isinf(osm_green.nearest_distance_m(far_pt, [])[0])
    ha = osm_green.area_per_cell_ha(grid, qual)
    assert abs(ha.sum() - sum(p.area for p in qual) / 1e4) < 0.2   # whole park lies inside the grid


def test_population_window(tmp_path, grid):
    # synthetic 100 m-ish raster covering the study area, every pixel = 2 people
    px = 0.0009
    w, s, e, n = 73.82, 18.48, 73.88, 18.54
    cols, rows = int((e - w) / px), int((n - s) / px)
    data = np.full((rows, cols), 2.0, dtype="float32")
    data[:3, :3] = -99999
    f = tmp_path / "pop.tif"
    with rasterio.open(f, "w", driver="GTiff", height=rows, width=cols, count=1, dtype="float32",
                       crs="EPSG:4326", transform=from_origin(w, n, px, px), nodata=-99999) as dst:
        dst.write(data, 1)
    p = population.load_population(CFG, grid, None, local_path=str(f))
    assert p["per_cell"].sum() == pytest.approx(p["total"])
    assert p["total"] == pytest.approx(2.0 * p["pixels"])
    assert p["pixels"] > 100
    qual = [Polygon([(grid.transform.c, grid.transform.f - 1000), (grid.transform.c + 800, grid.transform.f - 1000),
                     (grid.transform.c + 800, grid.transform.f - 1800), (grid.transform.c, grid.transform.f - 1800)])]
    acc = metrics.access_from_population(p, qual, 300, grid.n_cells)
    assert 0 < acc["pop_access"].sum() < p["total"]
    assert np.all(acc["pop_access"] <= p["per_cell"] + 1e-9)


def test_cell_table_and_summary(grid):
    n = grid.n_cells
    rng = np.random.default_rng(0)
    cols = {"tree_count": rng.integers(0, 50, n).astype(float), "lst_c": rng.uniform(30, 45, n),
            "pop": rng.uniform(0, 500, n), "builtup_pct": rng.uniform(0, 100, n)}
    cols["pop_access"] = cols["pop"] * 0.4
    df = metrics.cell_table(grid, cols)
    assert "tree_density_ha" in df and "access_share" in df
    assert np.allclose(df["tree_density_ha"], df["tree_count"] / (df["area_km2"] * 100))
    s = metrics.city_summary(df)
    assert s["trees_total"] == int(df["tree_count"].sum())
    assert s["pop_without_park_access_pct"] == pytest.approx(60.0, abs=0.2)
    assert s["lst_c_p10"] < s["lst_c_median"] < s["lst_c_p90"]
    assert 0 < s["pop_in_hottest_decile_cells"] < s["pop_total"]


def test_audit_flags_gaps():
    ctx = {"boundary": {"fallback": True, "source": "bbox", "area_km2": 1, "notes": []}, "n_cells": 5,
           "trees": {"rows_total": 100, "rows_valid_coords": 50, "rows_inside_study_area": 40, "n_parts_read": 1,
                     "coordinate_detection": ["x"]},
           "scene_counts": {"landsat": {"2024": 5}, "sentinel2": {"2024": 5}}}
    a = audit.build_audit(CFG, ctx)
    st = {c["id"]: c["status"] for c in a["checks"]}
    assert st["boundary"] == "warn" and st["trees"] == "fail" and st["satellite"] == "warn" and st["costs"] == "manual"


class _Resp:
    def __init__(self, payload): self._p = payload
    def raise_for_status(self): pass
    def json(self): return self._p


class _Sess:
    def __init__(self, payload=None, boom=False): self.payload, self.boom = payload, boom
    def get(self, *a, **k):
        if self.boom: raise RuntimeError("offline")
        return _Resp(self.payload)


def test_boundary_accepts_valid_and_falls_back():
    good = Polygon([(73.7, 18.4), (74.0, 18.4), (74.0, 18.65), (73.7, 18.65)])
    hit = {"category": "boundary", "osm_type": "relation", "osm_id": 1, "display_name": "Pune", "geojson": good.__geo_interface__}
    b = boundary.fetch_boundary(CFG, _Sess([hit]))
    assert not b["fallback"] and b["area_km2"] > 150
    tiny = Polygon([(73.85, 18.5), (73.86, 18.5), (73.86, 18.51), (73.85, 18.51)])
    hit2 = {**hit, "geojson": tiny.__geo_interface__}
    b2 = boundary.fetch_boundary(CFG, _Sess([hit2]))
    assert b2["fallback"] and "rejected" in " ".join(b2["notes"])
    b3 = boundary.fetch_boundary(CFG, _Sess(boom=True))
    assert b3["fallback"] and "failed" in " ".join(b3["notes"])


def test_run_end_to_end_records_failures(tmp_path, monkeypatch):
    """Orchestrator smoke test with the network replaced by local stand-ins.
    The satellite catalog 'fails' on purpose: the run must still finish and record the failure honestly."""
    monkeypatch.setattr(run, "fetch_boundary", lambda cfg, s: {"geometry": BOX, "source": "test box", "osm_ref": None,
                        "name": "t", "area_km2": 4.9, "fallback": True, "notes": []})
    csv = tmp_path / "t.csv"
    _write_trees(csv, [(18.51, 73.85)] * 4, "cols")
    real_count = tree_census.count_trees
    monkeypatch.setattr(run.tree_census, "count_trees", lambda cfg, g, s, wd=None: real_count(cfg, g, s, files=[csv]))
    monkeypatch.setattr(run.osm_green, "fetch_overpass", lambda cfg, bb, s: _overpass_json())
    monkeypatch.setattr(run.satellite, "open_catalog", lambda cfg: (_ for _ in ()).throw(RuntimeError("stac down")))
    px = 0.0009
    tif = tmp_path / "p.tif"
    with rasterio.open(tif, "w", driver="GTiff", height=80, width=80, count=1, dtype="float32", crs="EPSG:4326",
                       transform=from_origin(73.82, 18.54, px, px), nodata=-99999) as d:
        d.write(np.full((80, 80), 3.0, dtype="float32"), 1)
    real_pop = population.load_population
    monkeypatch.setattr(run.population, "load_population", lambda cfg, g, s: real_pop(cfg, g, s, local_path=str(tif)))
    monkeypatch.setenv("ECOMETRIX_ALLOW_PARTIAL", "1")
    out = tmp_path / "out"
    assert run.main(["--out", str(out), "--workdir", str(tmp_path / "raw")]) == 0
    man = json.loads((out / "manifest.json").read_text())
    assert man["layers"]["trees"]["status"] == "ok" and man["layers"]["osm"]["status"] == "ok"
    assert man["layers"]["landsat"]["status"] == "failed" and "stac down" in man["layers"]["landsat"]["reason"]
    df = pd.read_parquet(out / "cells.parquet")
    assert df["tree_count"].sum() == 4 and "ndvi" not in df.columns      # missing layer is absent, never invented
    summ = json.loads((out / "summary.json").read_text())
    assert summ["trees_total"] == 4 and "pop_without_park_access_pct" in summ
    assert (out / "audit.json").exists()


def test_open_land_and_unserved_nearby(grid):
    n = grid.n_cells
    cols = {"bare_pct": np.full(n, 10.0), "grass_pct": np.full(n, 20.0), "shrub_pct": np.full(n, 0.0),
            "park_ha": np.full(n, 1.0), "forest_ha": np.zeros(n)}
    df = metrics.cell_table(grid, cols)
    area_ha = df["area_km2"] * 100
    assert np.allclose(df["open_land_ha"], (0.30 * area_ha - 1.0).clip(lower=0))
    # four people in a row at 0, 100, 200, 400 m from the origin; the 400 m one is already served by a park
    xy = np.array([[0, 0], [100, 0], [200, 0], [400, 0.0]])
    people = np.array([10.0, 20.0, 30.0, 40.0])
    pix_dist = np.array([500.0, 500.0, 500.0, 100.0])      # last pixel is within 300 m of a park
    got = metrics.unserved_within(xy, people, pix_dist, 300, np.array([[0.0, 0.0], [390.0, 0.0]]), 300)
    assert got[0] == 60.0                                  # 10+20+30, the served pixel is excluded
    assert got[1] == 50.0                                  # 100 m and 200 m pixels lie within 300 m of x=390; the 400 m pixel is served
    assert metrics.unserved_within(xy, people, np.full(4, 10.0), 300, np.array([[0.0, 0.0]]), 300)[0] == 0.0


def test_population_series_reads_each_year_and_reports_missing(tmp_path, grid):
    px = 0.0009
    w, s, e, n = 73.82, 18.48, 73.88, 18.54
    cols, rows = int((e - w) / px), int((n - s) / px)
    for y, val in ((2018, 1.0), (2019, 2.0)):
        with rasterio.open(tmp_path / f"p{y}.tif", "w", driver="GTiff", height=rows, width=cols, count=1, dtype="float32",
                           crs="EPSG:4326", transform=from_origin(w, n, px, px), nodata=-99999) as d:
            d.write(np.full((rows, cols), val, dtype="float32"), 1)
    cfg = dict(CFG)
    cfg["population_series"] = {"url_template": str(tmp_path) + "/p{year}.tif", "years": [2018, 2019, 2020]}
    r = population.load_series(cfg, grid)
    assert sorted(r["per_cell_by_year"]) == [2018, 2019] and list(r["missing"]) == [2020]
    assert r["per_cell_by_year"][2019].sum() == pytest.approx(2 * r["per_cell_by_year"][2018].sum())


def test_unserved_pairs_match_the_aggregate_and_identify_shared_pixels():
    xy = np.array([[0, 0], [100, 0], [200, 0], [400, 0.0]]); people = np.array([10.0, 20.0, 30.0, 40.0])
    dist = np.array([500.0, 500.0, 500.0, 100.0])
    cent = np.array([[0.0, 0.0], [150.0, 0.0]])
    ci, pi = metrics.unserved_pairs(xy, people, dist, 300, cent, 300)
    agg = metrics.unserved_within(xy, people, dist, 300, cent, 300)
    for c in (0, 1):
        assert people[pi[ci == c]].sum() == agg[c]                 # pairs and aggregate agree exactly
    assert set(pi[ci == 0]) & set(pi[ci == 1]) == {0, 1, 2}        # all three unserved pixels are reachable from both sites
    assert 3 not in set(pi)                                        # the served pixel is never a catchment member
    e0, e1 = metrics.unserved_pairs(xy, people, np.full(4, 10.0), 300, cent, 300)
    assert e0.size == 0 and e1.size == 0
