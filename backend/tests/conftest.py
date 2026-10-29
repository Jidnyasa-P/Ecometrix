import json
import sys
from pathlib import Path
import numpy as np
import pandas as pd
import pytest
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


@pytest.fixture()
def data_dir(tmp_path):
    """A tiny pipeline-output folder built inside the test (test fixture only, never shipped)."""
    import h3
    centre = h3.latlng_to_cell(18.52, 73.85, 9)
    cells = sorted(h3.grid_disk(centre, 3))
    n = len(cells)
    rng = np.random.default_rng(3)
    ll = [h3.cell_to_latlng(c) for c in cells]
    df = pd.DataFrame({"h3": cells, "lat": [a for a, _ in ll], "lng": [b for _, b in ll], "area_km2": 0.1,
                       "tree_density_ha": rng.uniform(0, 30, n), "lst_c": rng.uniform(35, 45, n),
                       "pop": rng.uniform(0, 900, n), "access_share": rng.uniform(0, 1, n)})
    df.loc[0, "lst_c"] = np.nan
    df.to_parquet(tmp_path / "cells.parquet", index=False)
    (tmp_path / "manifest.json").write_text(json.dumps({"city": "T", "layers": {"trees": {"status": "ok"}}, "n_cells": n}))
    (tmp_path / "summary.json").write_text(json.dumps({"trees_total": 123}))
    (tmp_path / "audit.json").write_text(json.dumps({"checks": []}))
    return tmp_path


@pytest.fixture()
def full_dir(data_dir):
    """data_dir plus model outputs (analysis, sites, forecast), built inside the test."""
    df = pd.read_parquet(data_dir / "cells.parquet")
    n = len(df)
    rng = np.random.default_rng(5)
    an = pd.DataFrame({"h3": df["h3"], "pop_2035": df["pop"] * 1.4, "pop_growth_2035": df["pop"] * 0.4, "pop_unserved_2035": df["pop"] * 0.5,
                       "need_heat": rng.uniform(0, 1, n), "need_people": rng.uniform(0, 1, n), "need_gap": rng.uniform(0, 1, n),
                       "need_growth": rng.uniform(0, 1, n), "need_balanced": rng.uniform(0, 100, n), "need_no_regret": 0})
    an.to_parquet(data_dir / "analysis.parquet", index=False)
    s = pd.DataFrame({"site_id": [f"{h}:mini_forest" for h in df["h3"][:5]] + [f"{h}:pocket_park" for h in df["h3"][:5]],
                      "h3": list(df["h3"][:5]) * 2, "type": ["mini_forest"] * 5 + ["pocket_park"] * 5, "lat": 18.5, "lng": 73.8,
                      "area_ha": 1.0, "open_land_ha": 1.2, "cell_area_ha": 10.0, "pop": 400.0, "pop_unserved_300m": 250.0,
                      "ndvi_before": 0.2, "ndvi_after": 0.3, "dlst_p10": -0.8, "dlst_p50": -0.5, "dlst_p90": -0.2,
                      "verification": "candidate: needs field verification", "need_balanced": 60.0})
    s.loc[3, ["dlst_p10", "dlst_p50", "dlst_p90"]] = np.nan
    s.to_parquet(data_dir / "sites.parquet", index=False)
    (data_dir / "forecast.json").write_text(json.dumps({"status": "ok", "method": "linear_all"}))
    (data_dir / "models_manifest.json").write_text(json.dumps({"modules": {"sites": {"status": "ok"}}}))
    (data_dir / "heat_model.json").write_text(json.dumps({"status": "ok", "chosen": "linear_ndvi"}))
    (data_dir / "need_report.json").write_text(json.dumps({"stability": {"status": "ok"}}))
    return data_dir
