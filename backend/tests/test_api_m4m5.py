import pytest
from fastapi.testclient import TestClient
from app.main import create_app


def test_new_layers_appear_only_when_built(data_dir, tmp_path_factory):
    import shutil
    bare = tmp_path_factory.mktemp("bare")
    for n in ("cells.parquet", "manifest.json"):
        shutil.copy(data_dir / n, bare / n)                       # pipeline output only: no model outputs yet
    before = {f["key"] for f in TestClient(create_app(bare)).get("/api/meta").json()["fields"]}
    assert "need_balanced" not in before and "pop_2035" not in before
    import pandas as pd, numpy as np
    df = pd.read_parquet(data_dir / "cells.parquet")
    pd.DataFrame({"h3": df["h3"], "need_balanced": np.linspace(0, 100, len(df))}).to_parquet(bare / "analysis.parquet", index=False)
    after = {f["key"] for f in TestClient(create_app(bare)).get("/api/meta").json()["fields"]}
    assert "need_balanced" in after


def test_need_percentiles_are_scaled_to_100(data_dir, full_dir):
    f = {x["key"]: x for x in TestClient(create_app(full_dir)).get("/api/meta").json()["fields"]}
    assert f["need_heat"]["max"] > 1.5 and f["need_heat"]["max"] <= 100


def test_sites_columnar(full_dir):
    d = TestClient(create_app(full_dir)).get("/api/sites").json()
    assert d["n"] == 10 and len(d["columns"]["site_id"]) == 10
    assert d["columns"]["dlst_p50"][3] is None and d["columns"]["dlst_p50"][0] == -0.5


def test_scenario_run_returns_labelled_ranges(full_dir):
    c = TestClient(create_app(full_dir))
    sid = c.get("/api/sites").json()["columns"]["site_id"][0]
    r = c.post("/api/scenarios/run", json={"site_id": sid, "budget_inr": 1e9, "draws": 500})
    assert r.status_code == 200
    j = r.json()
    assert j["cost"]["evidence"] == "ASSUMED" and j["benefits"]["cooling"]["evidence"] == "MODELLED"
    assert j["cost"]["present_value_inr"]["p10"] < j["cost"]["present_value_inr"]["p90"]
    assert j["budget"]["probability_within_budget"] == 1.0
    assert "SIMULATED" in j["label_note"]


def test_scenario_errors_are_explicit(full_dir):
    c = TestClient(create_app(full_dir))
    sid = c.get("/api/sites").json()["columns"]["site_id"][0]
    assert c.post("/api/scenarios/run", json={"site_id": "nope"}).status_code == 404
    bad = c.post("/api/scenarios/run", json={"site_id": sid, "area_ha": 99})
    assert bad.status_code == 400 and bad.json()["detail"]["code"] == "invalid_scenario"
    assert c.post("/api/scenarios/run", json={"site_id": sid, "draws": 5}).status_code == 422


def test_site_without_cooling_is_reported_honestly(full_dir):
    c = TestClient(create_app(full_dir))
    sid = c.get("/api/sites").json()["columns"]["site_id"][3]
    j = c.post("/api/scenarios/run", json={"site_id": sid}).json()
    assert j["benefits"]["cooling"]["available"] is False


def test_other_endpoints(full_dir):
    c = TestClient(create_app(full_dir))
    assert c.get("/api/forecast").json()["method"] == "linear_all"
    assert c.get("/api/model-report").json()["heat_model"]["chosen"] == "linear_ndvi"
    a = c.get("/api/assumptions").json()
    assert "mini_forest" in a and a["pocket_park"]["carbon"]["estimated"] is False


def test_unbuilt_models_return_503_not_fake_data(tmp_path):
    c = TestClient(create_app(tmp_path))
    for path in ("/api/forecast", "/api/sites"):
        assert c.get(path).status_code == 503
    assert c.post("/api/scenarios/run", json={"site_id": "x"}).status_code == 503
    assert c.get("/api/model-report").json()["built"] is False
