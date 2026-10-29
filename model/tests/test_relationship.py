import sys
from pathlib import Path
import numpy as np
import pandas as pd
import h3
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from baseline_relationship import compute_relationship


def _cells(n_side=18, slope=-8.0, noise=0.0, seed=1):
    centre = h3.latlng_to_cell(18.52, 73.85, 9)
    ring = list(h3.grid_disk(centre, n_side))
    rng = np.random.default_rng(seed)
    ndvi = rng.uniform(0.05, 0.6, len(ring))
    lst = 45 + slope * ndvi + rng.normal(0, noise, len(ring))
    return pd.DataFrame({"h3": ring, "ndvi": ndvi, "lst_c": lst})


def test_recovers_known_slope_and_beats_mean_only():
    r = compute_relationship(_cells(slope=-8.0, noise=0.2), block_res=7)
    assert r["status"] == "ok"
    assert r["slope_c_per_0p1_ndvi"] == pytest_approx(-0.8, 0.05)
    assert r["pearson_r"] < -0.95
    assert r["spatial_block_cv"]["rmse_ndvi_model_c"] < r["spatial_block_cv"]["rmse_mean_only_c"]


def test_no_relationship_gives_no_improvement():
    r = compute_relationship(_cells(slope=0.0, noise=2.0), block_res=7)
    assert abs(r["pearson_r"]) < 0.15
    assert r["spatial_block_cv"]["rmse_improvement_pct"] < 2


def test_unavailable_when_columns_missing():
    r = compute_relationship(pd.DataFrame({"h3": ["x"], "ndvi": [0.1]}))
    assert r["status"] == "unavailable"


def pytest_approx(v, tol):
    import pytest
    return pytest.approx(v, abs=tol)
