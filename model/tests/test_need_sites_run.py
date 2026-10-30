import json
import sys
from pathlib import Path
import numpy as np
import pandas as pd
import h3
import pytest
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import need_score as ns
import sites as st
import run_models
import heat_model as hm

PRESETS = {"balanced": dict(heat=.25, people=.25, gap=.25, growth=.25), "heat_first": dict(heat=.7, people=.1, gap=.1, growth=.1)}


def cells_df(n_side=40, seed=3):
    centre = h3.latlng_to_cell(18.52, 73.85, 9)
    ring = sorted(h3.grid_disk(centre, n_side))
    rng = np.random.default_rng(seed); n = len(ring)
    ll = [h3.cell_to_latlng(c) for c in ring]
    ndvi = rng.uniform(0.05, 0.6, n); built = rng.uniform(0, 100, n); water = rng.uniform(0, 5, n)
    pop = rng.uniform(0, 800, n); pop[:25] = 0
    acc = rng.uniform(0, 1, n)
    lst = 38 - 6 * ndvi + 0.04 * built + rng.normal(0, 0.3, n)
    park = np.zeros(n); park[30:80] = 8.0; forest = np.zeros(n); forest[100:150] = 8.0
    return pd.DataFrame({"h3": ring, "lat": [a for a, _ in ll], "lng": [b for _, b in ll], "area_km2": 0.1, "ndvi": ndvi,
                         "builtup_pct": built, "water_pct": water, "lst_c": lst, "pop": pop, "access_share": acc,
                         "pop_unserved_300m": pop * (1 - acc), "park_ha": park, "forest_ha": forest,
                         "open_land_ha": rng.uniform(0, 3, n)})


def test_components_are_ranks_and_unpopulated_cells_unscored():
    c = cells_df()
    d = ns.components(c, None, None)
    assert set(ns.available(d)) == {"heat", "people", "gap"}          # growth absent: no forecast supplied, and that is reported
    assert d["need_heat"].dropna().between(0, 1).all()
    assert d.loc[c["pop"] == 0, "need_heat"].isna().all()
    s = ns.score(d, PRESETS["balanced"])
    assert s.dropna().between(0, 100).all() and s[c["pop"] == 0].isna().all()


def test_score_is_monotone_in_each_component_and_renormalises_weights():
    c = cells_df(); d = ns.components(c, None, None)
    hot = d["need_heat"].idxmax(); cold = d["need_heat"].idxmin()
    d.loc[[hot, cold], ["need_people", "need_gap"]] = 0.5                 # equal on the other components
    s = ns.score(d, {"heat": 1.0, "people": 1.0, "gap": 1.0, "growth": 1.0})
    assert s[hot] > s[cold]
    only_heat = ns.score(d, {"heat": 1.0})
    assert only_heat[hot] == pytest.approx(100 * d.loc[hot, "need_heat"])


def test_stability_report_and_no_regret_subset():
    c = cells_df(); d = ns.components(c, None, None)
    r = ns.stability(d, PRESETS)
    assert r["status"] == "ok" and -1 <= r["pairs"][0]["spearman"] <= 1
    flags = ns.no_regret_flags(d, PRESETS)
    assert flags.sum() == r["no_regret_cells"] and flags.sum() <= max(1, int(r["scored_cells"] * 0.10))


def test_sites_rules_and_cooling_sign():
    c = cells_df(); d = ns.components(c, None, None)
    heat = hm.run(c); targets = hm.greenness_targets(c)
    cand = {"pocket_park": {"min_site_ha": 0.5, "max_site_ha": 2.0}, "mini_forest": {"min_site_ha": 0.1, "max_site_ha": 1.0}}
    s = st.build(c, d, heat, targets, cand)
    assert set(s["type"]) == {"pocket_park", "mini_forest"}
    pp = s[s.type == "pocket_park"]
    assert (pp.area_ha >= 0.5).all() and (pp.area_ha <= 2.0).all() and (s[s.type == "mini_forest"].area_ha <= 1.0).all()
    assert (s["pop"] > 0).all()                                            # unpopulated hexagons never become candidates
    assert (s.verification == "candidate: needs field verification").all()
    assert (s.dlst_p50.dropna() <= 1e-9).all()                             # greener never means hotter
    assert (s.dlst_p10 <= s.dlst_p50 + 1e-9).all() and (s.dlst_p50 <= s.dlst_p90 + 1e-9).all()
    big = s.sort_values("area_ha").iloc[-1]; small = s.sort_values("area_ha").iloc[0]
    assert big.ndvi_after >= big.ndvi_before and small.ndvi_after >= small.ndvi_before


def test_sites_without_a_greenness_target_have_no_cooling_estimate_not_a_fake_one():
    c = cells_df(); c["park_ha"] = 0.0; c["forest_ha"] = 0.0           # no park-like cells anywhere: no data-derived target
    d = ns.components(c, None, None)
    heat = hm.run(c); targets = hm.greenness_targets(c)
    cand = {"pocket_park": {"min_site_ha": 0.5, "max_site_ha": 2.0}, "mini_forest": {"min_site_ha": 0.1, "max_site_ha": 1.0}}
    s = st.build(c, d, heat, targets, cand)
    assert s["dlst_p50"].isna().all()


def test_run_models_end_to_end_records_missing_pieces(tmp_path):
    c = cells_df(n_side=30)
    c.to_parquet(tmp_path / "cells.parquet", index=False)
    years = list(range(2000, 2021)); rng = np.random.default_rng(1)
    ps = pd.DataFrame({"h3": c["h3"]})
    base = rng.uniform(20, 300, len(c))
    for y in years:
        ps[f"y{y}"] = base * (1 + 0.03 * (y - 2000)) * (1 + rng.normal(0, 0.02, len(c)))
    ps.to_parquet(tmp_path / "popseries.parquet", index=False)
    assert run_models.main([str(tmp_path)]) == 0
    man = json.loads((tmp_path / "models_manifest.json").read_text())["modules"]
    assert all(man[k]["status"] == "ok" for k in ("heat_model", "forecast", "need_score", "sites"))
    a = pd.read_parquet(tmp_path / "analysis.parquet")
    assert {"need_heat", "need_growth", "need_balanced", "pop_2035", "pop_unserved_2035", "need_no_regret"} <= set(a.columns)
    assert (tmp_path / "heat_model.json").exists() and (tmp_path / "forecast.json").exists()
    f = json.loads((tmp_path / "forecast.json").read_text())
    assert f["status"] == "ok" and "_cells" not in f
    # no yearly population layer: forecast is reported as failed, growth component absent, everything else still works
    (tmp_path / "popseries.parquet").unlink()
    assert run_models.main([str(tmp_path)]) == 0
    man2 = json.loads((tmp_path / "models_manifest.json").read_text())["modules"]
    assert man2["forecast"]["status"] == "failed" and man2["sites"]["status"] == "ok"
    # A missing current input must not leave the previous run's forecast available.
    assert not (tmp_path / "forecast.json").exists()
    assert "need_growth" not in pd.read_parquet(tmp_path / "analysis.parquet").columns
