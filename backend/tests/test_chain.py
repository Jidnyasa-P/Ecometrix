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


@pytest.fixture()
def chain_dir(tmp_path):
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
