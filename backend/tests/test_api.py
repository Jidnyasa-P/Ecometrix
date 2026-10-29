import json
import pytest
from fastapi.testclient import TestClient
from app.main import create_app


def test_health_and_meta_with_data(data_dir):
    c = TestClient(create_app(data_dir))
    assert c.get("/api/health").json() == {"status": "ok", "data_loaded": True}
    m = c.get("/api/meta").json()
    keys = {f["key"] for f in m["fields"]}
    assert keys == {"tree_density_ha", "lst_c", "pop", "access_share"}          # only fields present in the data
    lst = next(f for f in m["fields"] if f["key"] == "lst_c")
    assert 35 <= lst["domain"][0] < lst["domain"][1] <= 45 and lst["evidence"] == "MEASURED"
    acc = next(f for f in m["fields"] if f["key"] == "access_share")
    assert acc["max"] <= 100 and acc["max"] > 1                                 # shown as percent


def test_cells_columnar_nan_becomes_null(data_dir):
    c = TestClient(create_app(data_dir))
    r = c.get("/api/cells")
    assert r.status_code == 200
    d = r.json()
    assert d["n"] == len(d["h3"]) == len(d["values"]["lst_c"])
    assert d["values"]["lst_c"][0] is None
    assert all(len(v) == d["n"] for v in d["values"].values())


def test_cell_detail_and_404(data_dir):
    c = TestClient(create_app(data_dir))
    hid = c.get("/api/cells").json()["h3"][5]
    r = c.get(f"/api/cells/{hid}")
    assert r.status_code == 200 and r.json()["h3"] == hid
    assert c.get("/api/cells/doesnotexist").status_code == 404


def test_missing_data_is_reported_not_faked(tmp_path):
    c = TestClient(create_app(tmp_path))
    assert c.get("/api/health").json()["data_loaded"] is False
    assert c.get("/api/meta").json()["built"] is False
    for path in ("/api/cells", "/api/summary", "/api/audit", "/api/relationship"):
        r = c.get(path)
        assert r.status_code == 503 and r.json()["detail"]["code"] == "baseline_not_built"


def test_cors_allows_configured_origin(data_dir, monkeypatch):
    monkeypatch.setenv("ALLOWED_ORIGINS", "https://ecometrix.vercel.app")
    c = TestClient(create_app(data_dir))
    r = c.get("/api/health", headers={"Origin": "https://ecometrix.vercel.app"})
    assert r.headers["access-control-allow-origin"] == "https://ecometrix.vercel.app"
    r2 = c.get("/api/health", headers={"Origin": "https://evil.example"})
    assert "access-control-allow-origin" not in r2.headers


def test_reload_when_files_change(data_dir):
    c = TestClient(create_app(data_dir))
    assert c.get("/api/summary").json()["trees_total"] == 123
    # data refresh = new files on disk; the store picks up new parquet/manifest by mtime
    import os, time
    m = data_dir / "manifest.json"
    time.sleep(0.01); m.write_text(json.dumps({"city": "T2", "layers": {}, "n_cells": 1}))
    os.utime(m, (time.time() + 5, time.time() + 5))
    assert c.get("/api/meta").json()["manifest"]["city"] == "T2"
