"""M4: the heat-greenery model.

Question: across the selected city's hexagons, how does pre-monsoon surface temperature (LST) change with vegetation (NDVI),
holding built-up share and water share fixed, and what would LST be if a site became greener?

Rules from the roadmap, enforced in code:
  * every model is compared with simple baselines; the machine-learning model is kept ONLY if it wins
  * validation is spatial block cross-validation (whole neighbourhoods held out), never random splits
  * the model must not predict that more vegetation makes a place hotter (monotonic constraint + explicit check)
  * what is reported is an association learned from satellite data, not proof of cooling by new planting
"""
from __future__ import annotations
import h3
import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.inspection import permutation_importance
from sklearn.linear_model import LinearRegression
from sklearn.model_selection import GroupKFold

FEATURES = ["ndvi", "builtup_pct", "water_pct"]
BLOCK_RES = 6          # H3 resolution for spatial blocks (about 36 km2)
SEED = 42


def prepare(cells: pd.DataFrame) -> pd.DataFrame:
    need = FEATURES + ["lst_c", "h3"]
    missing = [c for c in need if c not in cells.columns]
    if missing:
        raise ValueError(f"heat model needs columns {missing}; build those layers first")
    d = cells[need].replace([np.inf, -np.inf], np.nan).dropna().reset_index(drop=True)
    d["block"] = d["h3"].map(lambda c: h3.cell_to_parent(c, BLOCK_RES))
    return d


def make_model(kind: str):
    if kind == "mean_only":
        return _MeanOnly()
    if kind == "linear_ndvi":
        return _Sub(LinearRegression(), [0])
    if kind == "linear_multi":
        return LinearRegression()
    if kind == "hgb_monotone":
        # NDVI up -> LST down (-1); built-up up -> LST up (+1); water up -> LST down (-1)
        return HistGradientBoostingRegressor(max_iter=200, learning_rate=0.06, max_depth=4, min_samples_leaf=20,
                                             monotonic_cst=[-1, 1, -1], random_state=SEED)
    raise KeyError(kind)


class _MeanOnly:
    def fit(self, X, y): self.m = float(np.mean(y)); return self
    def predict(self, X): return np.full(len(X), self.m)


class _Sub:
    """Fit/predict a model on a subset of feature columns."""
    def __init__(self, m, cols): self.m, self.cols = m, cols
    def fit(self, X, y): self.m.fit(np.asarray(X)[:, self.cols], y); return self
    def predict(self, X): return self.m.predict(np.asarray(X)[:, self.cols])


MODEL_ORDER = ["mean_only", "linear_ndvi", "linear_multi", "hgb_monotone"]   # simplest first


def spatial_cv(d: pd.DataFrame, kinds=MODEL_ORDER, folds: int = 5) -> dict:
    X, y, g = d[FEATURES].to_numpy(float), d["lst_c"].to_numpy(float), d["block"].to_numpy()
    n_groups = len(set(g))
    if n_groups < 3:
        return {"status": "unavailable", "reason": f"only {n_groups} spatial blocks; need at least 3 for spatial validation"}
    k = min(folds, n_groups)
    out = {"blocks": int(n_groups), "folds": int(k), "cells": int(len(d)), "models": {}}
    for kind in kinds:
        pred = np.full(len(y), np.nan)
        for tr, te in GroupKFold(n_splits=k).split(X, y, g):
            pred[te] = make_model(kind).fit(X[tr], y[tr]).predict(X[te])
        err = y - pred
        ss_tot = float(((y - y.mean()) ** 2).sum())
        out["models"][kind] = {"rmse_c": round(float(np.sqrt(np.mean(err ** 2))), 4), "mae_c": round(float(np.mean(np.abs(err))), 4),
                               "r2": round(1 - float((err ** 2).sum()) / ss_tot, 4) if ss_tot > 0 else None}
    return {"status": "ok", **out}


def choose(cv: dict, min_gain: float = 0.01) -> str:
    """Lowest cross-validated RMSE wins, but a more complex model must beat the best simpler one by at least `min_gain` (1%)."""
    best, best_rmse = None, None
    for kind in MODEL_ORDER:
        if kind == "mean_only" or kind not in cv["models"]:
            continue
        r = cv["models"][kind]["rmse_c"]
        if best is None or r < best_rmse * (1 - min_gain):
            best, best_rmse = kind, r
    mean_r = cv["models"]["mean_only"]["rmse_c"]
    return best if best is not None and best_rmse < mean_r else "mean_only"


def monotonic_check(model, d: pd.DataFrame) -> dict:
    """Predict along an NDVI sweep with other features at their medians; LST must never rise with NDVI."""
    grid = np.linspace(d["ndvi"].quantile(0.02), d["ndvi"].quantile(0.98), 40)
    X = np.tile(d[FEATURES].median().to_numpy(float), (len(grid), 1))
    X[:, 0] = grid
    p = model.predict(X)
    rises = float(np.max(np.diff(p))) if len(p) > 1 else 0.0
    return {"ok": bool(rises <= 1e-9), "max_rise_c": round(rises, 6), "sweep_change_c": round(float(p[-1] - p[0]), 3)}


def importance(kind: str, d: pd.DataFrame) -> dict:
    """Permutation importance on held-out blocks (increase in RMSE when a feature is shuffled)."""
    X, y, g = d[FEATURES].to_numpy(float), d["lst_c"].to_numpy(float), d["block"].to_numpy()
    if len(set(g)) < 3:
        return {}
    tr, te = next(GroupKFold(n_splits=min(5, len(set(g)))).split(X, y, g))
    m = make_model(kind).fit(X[tr], y[tr])
    if kind in ("mean_only",):
        return {}
    class W:  # sklearn scorer wrapper for our light classes
        def __init__(self, m): self.m = m
        def fit(self, *a): return self
        def predict(self, X): return self.m.predict(X)
        def score(self, X, y): return -float(np.sqrt(np.mean((y - self.m.predict(X)) ** 2)))
    r = permutation_importance(W(m), X[te], y[te], n_repeats=15, random_state=SEED)
    return {f: round(float(v), 4) for f, v in zip(FEATURES, r.importances_mean)}


def bootstrap_models(kind: str, d: pd.DataFrame, n: int = 40) -> list:
    """Models refit on block-bootstrap resamples (whole spatial blocks drawn with replacement)."""
    rng = np.random.default_rng(SEED)
    blocks = d["block"].unique()
    groups = {b: np.flatnonzero(d["block"].to_numpy() == b) for b in blocks}
    X, y = d[FEATURES].to_numpy(float), d["lst_c"].to_numpy(float)
    models = []
    for _ in range(n):
        pick = rng.choice(blocks, size=len(blocks), replace=True)
        idx = np.concatenate([groups[b] for b in pick])
        models.append(make_model(kind).fit(X[idx], y[idx]))
    return models


def delta_lst(models: list, X_before: np.ndarray, X_after: np.ndarray) -> np.ndarray:
    """Predicted LST change (negative = cooler) for each row, one row per bootstrap model."""
    return np.vstack([m.predict(X_after) - m.predict(X_before) for m in models])


def greenness_targets(cells: pd.DataFrame, min_cells: int = 10, share: float = 0.5) -> dict:
    """Typical NDVI of cells that are mostly mapped park / mostly mapped forest: a DATA-DERIVED target for what a new
    park or mini-forest looks like from space. No literature constant is used."""
    out = {}
    area_ha = cells["area_km2"] * 100.0
    for name, col in (("pocket_park", "park_ha"), ("mini_forest", "forest_ha")):
        if col not in cells.columns or "ndvi" not in cells.columns:
            out[name] = {"available": False, "reason": f"needs columns {col} and ndvi"}
            continue
        m = (cells[col] / area_ha >= share) & cells["ndvi"].notna()
        if int(m.sum()) < min_cells:
            out[name] = {"available": False, "reason": f"only {int(m.sum())} cells are at least {int(share*100)}% mapped {col.split('_')[0]}; need {min_cells}"}
        else:
            v = cells.loc[m, "ndvi"]
            out[name] = {"available": True, "ndvi_target": round(float(v.median()), 4), "cells": int(m.sum()),
                         "ndvi_p25": round(float(v.quantile(.25)), 4), "ndvi_p75": round(float(v.quantile(.75)), 4)}
    return out


def run(cells: pd.DataFrame) -> dict:
    d = prepare(cells)
    cv = spatial_cv(d)
    if cv["status"] != "ok":
        return {"status": "unavailable", "reason": cv["reason"]}
    kind = choose(cv)
    final = make_model(kind).fit(d[FEATURES].to_numpy(float), d["lst_c"].to_numpy(float))
    base = cv["models"]["linear_ndvi"]["rmse_c"]
    chosen = cv["models"][kind]["rmse_c"]
    return {"status": "ok", "chosen": kind, "features": FEATURES, "cv": cv, "monotonic": monotonic_check(final, d),
            "importance_heldout_rmse_increase_c": importance(kind, d),
            "gain_vs_linear_ndvi_pct": round(100 * (base - chosen) / base, 2) if base else None,
            "note": "Association learned from satellite data. LST is a mid-morning SURFACE temperature, not air temperature.",
            "_d": d, "_final": final}
