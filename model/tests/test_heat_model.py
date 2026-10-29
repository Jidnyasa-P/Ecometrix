import sys
from pathlib import Path
import numpy as np
import pandas as pd
import h3
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import heat_model as hm


def synth(n_side=40, nonlinear=False, seed=1, noise=0.3):
    centre = h3.latlng_to_cell(18.52, 73.85, 9)
    ring = sorted(h3.grid_disk(centre, n_side))
    rng = np.random.default_rng(seed)
    ndvi = rng.uniform(0.05, 0.6, len(ring)); built = rng.uniform(0, 100, len(ring)); water = rng.uniform(0, 5, len(ring))
    lst = 38 - 6 * ndvi + 0.04 * built - 0.1 * water + rng.normal(0, noise, len(ring))
    if nonlinear:
        lst = lst - 3 * np.minimum(ndvi, 0.25) * (built / 100)          # interaction a straight line cannot capture
    return pd.DataFrame({"h3": ring, "ndvi": ndvi, "builtup_pct": built, "water_pct": water, "lst_c": lst,
                         "area_km2": 0.1, "park_ha": 0.0, "forest_ha": 0.0})


def test_linear_world_keeps_the_simple_model():
    r = hm.run(synth())
    assert r["status"] == "ok"
    ms = r["cv"]["models"]
    assert ms["linear_ndvi"]["rmse_c"] < ms["mean_only"]["rmse_c"]
    assert r["chosen"] in ("linear_multi", "linear_ndvi")        # the ML model must NOT be chosen when it does not clearly win
    assert r["monotonic"]["ok"]


def test_ml_model_chosen_only_when_it_wins():
    r = hm.run(synth(nonlinear=True, noise=0.1))
    ms = r["cv"]["models"]
    if r["chosen"] == "hgb_monotone":
        assert ms["hgb_monotone"]["rmse_c"] < ms["linear_multi"]["rmse_c"] * 0.99
    assert r["monotonic"]["ok"] and r["monotonic"]["sweep_change_c"] < 0


def test_choose_rule_prefers_simple_on_small_gain():
    cv = {"models": {"mean_only": {"rmse_c": 3.0}, "linear_ndvi": {"rmse_c": 1.00}, "linear_multi": {"rmse_c": 0.995}, "hgb_monotone": {"rmse_c": 0.99}}}
    assert hm.choose(cv) == "linear_ndvi"
    cv["models"]["hgb_monotone"]["rmse_c"] = 0.80
    assert hm.choose(cv) == "hgb_monotone"
    cv["models"] = {"mean_only": {"rmse_c": 1.0}, "linear_ndvi": {"rmse_c": 1.2}, "linear_multi": {"rmse_c": 1.3}, "hgb_monotone": {"rmse_c": 1.4}}
    assert hm.choose(cv) == "mean_only"


def test_spatial_cv_refuses_with_too_few_blocks():
    d = hm.prepare(synth(n_side=3))
    assert hm.spatial_cv(d)["status"] == "unavailable"


def test_counterfactual_delta_sign_and_size():
    df = synth()
    r = hm.run(df)
    ms = hm.bootstrap_models(r["chosen"], r["_d"], n=10)
    Xb = np.array([[0.10, 50.0, 0.0]]); Xa = np.array([[0.30, 50.0, 0.0]])
    dl = hm.delta_lst(ms, Xb, Xa)
    assert dl.shape == (10, 1) and np.all(dl < 0)
    assert abs(np.median(dl) - (-6 * 0.2)) < 0.5                  # truth is -6 C per 1.0 NDVI: -1.2 C for +0.2
    assert np.allclose(hm.delta_lst(ms, Xb, Xb), 0.0)             # no change in greenness, no change in temperature


def test_greenness_targets_data_derived_and_guarded():
    df = synth(); df["area_km2"] = 0.1
    df.loc[:30, "park_ha"] = 8.0                                   # 0.1 km2 = 10 ha, so 80% park
    t = hm.greenness_targets(df)
    assert t["pocket_park"]["available"] and abs(t["pocket_park"]["ndvi_target"] - df.loc[:30, "ndvi"].median()) < 1e-3
    assert t["mini_forest"]["available"] is False
