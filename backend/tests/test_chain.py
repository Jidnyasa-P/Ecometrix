"""Whole chain on stand-in data built inside the test: pipeline-shaped outputs -> model step -> API -> scenario on a returned site."""
import sys
from pathlib import Path
import h3
import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "model"))
import run_models  # noqa: E402
from app.main import create_app  # noqa: E402


@pytest.fixture(scope="module")
def chain_dir(tmp_path_factory):
    tmp_path = tmp_path_factory.mktemp("chain")
    centre = h3.latlng_to_cell(18.52, 73.85, 9)
    ring = sorted(h3.grid_disk(centre, 35))
    n = len(ring); rng = np.random.default_rng(11)
    ll = [h3.cell_to_latlng(c) for c in ring]
    ndvi = rng.uniform(0.05, 0.6, n); built = rng.uniform(0, 100, n); water = rng.uniform(0, 4, n)
    pop = rng.uniform(0, 900, n); pop[:20] = 0
    acc = rng.uniform(0, 1, n)
    df = pd.DataFrame({"h3": [h3.int_to_str(c) if isinstance(c, int) else c for c in ring], "lat": [a for a, _ in ll], "lng": [b for _, b in ll], "area_km2": 0.0986,
                       "tree_count": rng.integers(0, 200, n).astype(float), "ndvi": ndvi, "builtup_pct": built, "water_pct": water,
                       "bare_pct": rng.uniform(0, 15, n), "grass_pct": rng.uniform(0, 25, n), "shrub_pct": rng.uniform(0, 10, n),
                       "lst_c": 39 - 6 * ndvi + 0.04 * built + rng.normal(0, 0.3, n), "pop": pop, "pop_access": pop * acc,
                       "park_ha": np.where(np.arange(n) % 9 == 0, 6.0, 0.0), "forest_ha": np.where(np.arange(n) % 11 == 0, 6.0, 0.0),
                       "dist_park_m": rng.uniform(0, 2500, n)})
    df["access_share"] = np.where(df["pop"] > 0, df["pop_access"] / df["pop"], np.nan)
    df["pop_unserved_300m"] = df["pop"] * (1 - acc) * 1.5
    area_ha = df["area_km2"] * 100
    df["open_land_ha"] = ((df["bare_pct"] + df["grass_pct"] + df["shrub_pct"]) / 100 * area_ha - df["park_ha"] - df["forest_ha"]).clip(lower=0)
    df.loc[5, "ndvi"] = np.nan                                                  # a hexagon with a missing satellite value
    df.to_parquet(tmp_path / "cells.parquet", index=False)
    ps = pd.DataFrame({"h3": df["h3"]}); base = rng.uniform(30, 400, n)
    for y in range(2000, 2021):
        ps[f"y{y}"] = base * (1 + 0.025 * (y - 2000)) * (1 + rng.normal(0, 0.02, n))
    ps.to_parquet(tmp_path / "popseries.parquet", index=False)
    # exact catchments as the pipeline would write them: each hexagon reaches a few unserved pixels, shared with its neighbours
    rows = []
    for i, h in enumerate(df["h3"]):
        for k in range(i * 2, i * 2 + 5):
            rows.append((h, k, 5.0 + (k % 7) * 3))
    sp = pd.DataFrame(rows, columns=["h3", "pixel", "people"])
    sp["people"] = sp["pixel"].map(sp.drop_duplicates("pixel").set_index("pixel")["people"])
    sp.to_parquet(tmp_path / "site_pixels.parquet", index=False)
    import yaml, os
    cfg = yaml.safe_load((ROOT / "config" / "pilot_pune.yaml").read_text())
    cfg["portfolio"].update({"budget_multiples_of_median_site_cost": [5, 20], "equity_shares_pct": [0, 50], "solver_time_limit_s": 2,
                             "presets": {"balanced": cfg["portfolio"]["presets"]["balanced"], "heat_first": cfg["portfolio"]["presets"]["heat_first"]}})
    (tmp_path / "test_config.yaml").write_text(yaml.safe_dump(cfg))
    os.environ["ECOMETRIX_CONFIG"] = str(tmp_path / "test_config.yaml")
    (tmp_path / "manifest.json").write_text('{"city":"T","layers":{},"n_cells":%d}' % n)
    assert run_models.main([str(tmp_path)]) == 0
    return tmp_path


def test_chain_end_to_end(chain_dir):
    c = TestClient(create_app(chain_dir))
    meta = c.get("/api/meta").json()
    keys = {f["key"] for f in meta["fields"]}
    assert {"need_balanced", "need_heat", "pop_2035", "pop_growth_2035", "pop_unserved_2035", "lst_c"} <= keys
    cells = c.get("/api/cells").json()
    assert cells["n"] == len(cells["h3"]) and all(len(v) == cells["n"] for v in cells["values"].values())
    sites = c.get("/api/sites").json()
    cols = sites["columns"]
    assert sites["n"] > 10 and set(cols["type"]) == {"pocket_park", "mini_forest"}
    assert all(h in set(cells["h3"]) for h in cols["h3"])                       # every site sits in a known hexagon
    # run a scenario for one site of each type and check the results are coherent
    for t in ("pocket_park", "mini_forest"):
        i = next(k for k, v in enumerate(cols["type"]) if v == t and cols["dlst_p50"][k] is not None)
        r = c.post("/api/scenarios/run", json={"site_id": cols["site_id"][i], "budget_inr": 5e7, "draws": 400})
        assert r.status_code == 200, r.text
        j = r.json()
        pv = j["cost"]["present_value_inr"]
        assert 0 < pv["p10"] < pv["p50"] < pv["p90"]
        assert j["benefits"]["cooling"]["delta_lst_c"]["p50"] <= 0
        if t == "pocket_park":
            assert j["benefits"]["carbon"]["available"] is False
        else:
            assert j["benefits"]["carbon"]["t_co2e"]["p50"] > 0 and j["benefits"]["people_newly_served"]["value"] == 0
    rep = c.get("/api/model-report").json()
    assert rep["modules"]["heat_model"]["status"] == "ok" and rep["heat_model"]["cv"]["models"]
    assert c.get("/api/forecast").json()["method"] in ("naive", "linear_recent10", "linear_all", "exponential_all")


def test_cell_with_missing_satellite_value_is_null_not_zero(chain_dir):
    c = TestClient(create_app(chain_dir))
    d = c.get("/api/cells").json()
    if "ndvi" in d["values"]:
        assert d["values"]["ndvi"][5] is None


def test_portfolios_and_sensitivity_are_served_and_coherent(chain_dir):
    c = TestClient(create_app(chain_dir))
    p = c.get("/api/portfolios").json()
    assert p["status"] == "ok" and p["candidate_sites"] > 10 and len(p["results"]) == 2 * len(p["budgets_inr"]) * 2
    for r in p["results"]:
        assert r["solver"]["status"] in ("OPTIMAL", "FEASIBLE")
        assert r["cost_pv_inr"]["p50"] <= r["budget_inr"] * 1.5                          # median cost near or under the budget (MC sums can exceed it)
        assert r["people_newly_served"] >= 0 and 0 <= r["prob_within_budget"] <= 1
        if r["equity_pct"] == 0 and r["gain_vs_top_need_pct"] is not None:
            assert r["gain_vs_top_need_pct"] >= -1e-6
    ids = {s["site_id"] for s in c.get("/api/sites").json()["columns"]["site_id"] and [{"site_id": x} for x in c.get("/api/sites").json()["columns"]["site_id"]]}
    assert all(s["site_id"] in ids for r in p["results"] for s in r["sites"])
    sv = c.get("/api/sensitivity").json()
    assert sv["status"] == "ok" and sv["types"]["mini_forest"]["rows"][0]["max_relative_swing"] >= sv["types"]["mini_forest"]["rows"][-1]["max_relative_swing"]
    assert c.get("/api/model-report").json()["modules"]["portfolio"]["status"] == "ok"
