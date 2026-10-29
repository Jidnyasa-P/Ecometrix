"""M5: demand forecast. Population per hexagon to 2025, 2030 and 2035, from WorldPop's yearly series (2000-2020).

Honest limits, built into the output:
  * the history is itself a MODEL product (WorldPop), so this is a forecast of a modelled series
  * methods are simple on purpose (naive, straight line, exponential); the winner is chosen by a BACKTEST on years the
    model never saw, and a more complex method has to beat "no change" to be used at all
  * the uncertainty band is a BACKTEST ERROR ENVELOPE (smallest and largest relative error seen at each horizon across
    several forecast origins). It is not a statistical interval, and beyond the tested horizon it is extended linearly
  * policy shocks (new metro line, master-plan change) are not captured
"""
from __future__ import annotations
import numpy as np
import pandas as pd

METHODS = ["naive", "linear_recent10", "linear_all", "exponential_all"]   # simplest first


def _ols(Y: np.ndarray, years: np.ndarray, target: np.ndarray) -> np.ndarray:
    xc = years - years.mean()
    slope = (Y - Y.mean(axis=1, keepdims=True)) @ xc / np.sum(xc ** 2)
    return Y.mean(axis=1, keepdims=True) + slope[:, None] * (target - years.mean())[None, :]


def predict(method: str, Y: np.ndarray, years: np.ndarray, target: np.ndarray) -> np.ndarray:
    """Y: cells x years (history); returns cells x len(target), never negative."""
    years, target = np.asarray(years, float), np.asarray(target, float)
    if method == "naive":
        P = np.repeat(Y[:, -1:], len(target), axis=1)
    elif method == "linear_all":
        P = _ols(Y, years, target)
    elif method == "linear_recent10":
        k = min(10, len(years))
        P = _ols(Y[:, -k:], years[-k:], target)
    elif method == "exponential_all":
        pos = np.all(Y > 0, axis=1)
        P = _ols(Y, years, target)                                   # fallback for cells with zeros
        if pos.any():
            P[pos] = np.exp(_ols(np.log(Y[pos]), years, target))
    else:
        raise KeyError(method)
    return np.clip(P, 0, None)


def _wape(actual: np.ndarray, pred: np.ndarray) -> float:
    d = np.abs(actual).sum()
    return float(np.abs(actual - pred).sum() / d * 100) if d > 0 else float("nan")


def backtest(Y: np.ndarray, years: np.ndarray, train_until: int) -> dict:
    tr = years <= train_until
    te = ~tr
    if tr.sum() < 6 or te.sum() < 2:
        raise ValueError("not enough years for a backtest")
    res = {}
    for m in METHODS:
        P = predict(m, Y[:, tr], years[tr], years[te])
        A = Y[:, te]
        city_p, city_a = P.sum(axis=0), A.sum(axis=0)
        res[m] = {"wape_pct": round(_wape(A, P), 3),
                  "city_mape_pct": round(float(np.mean(np.abs(city_a - city_p) / city_a) * 100), 3),
                  "city_bias_pct": round(float(np.mean((city_p - city_a) / city_a) * 100), 3),
                  "wape_by_horizon_pct": [round(_wape(A[:, i], P[:, i]), 3) for i in range(A.shape[1])]}
    return {"train_years": [int(years[tr][0]), int(years[tr][-1])], "test_years": [int(y) for y in years[te]], "methods": res}


def choose(bt: dict, min_gain: float = 0.01) -> str:
    best, best_w = None, None
    for m in METHODS:
        w = bt["methods"][m]["wape_pct"]
        if best is None or w < best_w * (1 - min_gain):
            best, best_w = m, w
    return best


def envelope(Y: np.ndarray, years: np.ndarray, method: str, origins: list[int], max_h: int) -> dict:
    """Relative error of the CITY TOTAL by horizon across forecast origins: {h: [min_err, max_err]} (err = (pred-actual)/actual)."""
    errs: dict[int, list[float]] = {}
    for o in origins:
        tr = years <= o
        te = years > o
        if tr.sum() < 6 or te.sum() < 1:
            continue
        P = predict(method, Y[:, tr], years[tr], years[te]).sum(axis=0)
        A = Y[:, te].sum(axis=0)
        for h, (p, a) in enumerate(zip(P, A), start=1):
            errs.setdefault(h, []).append(float((p - a) / a))
    if not errs:
        return {"observed": {}, "per_year_growth": 0.0}
    obs = {h: [min(v), max(v)] for h, v in errs.items()}
    hmax = max(obs)
    worst = max(max(abs(x) for x in obs[hmax]), 1e-9)
    return {"observed": obs, "per_year_growth": worst / hmax}


def band(env: dict, h: int) -> tuple[float, float]:
    """Relative range of (pred-actual)/actual at horizon h; beyond the tested horizon the worst case grows linearly."""
    obs = env["observed"]
    if not obs:
        return (0.0, 0.0)
    if h in obs:
        lo, hi = obs[h]
    else:
        hmax = max(obs)
        w = env["per_year_growth"] * h
        lo, hi = -w, w
    lo, hi = min(lo, -abs(hi) * 0 - 1e-12), max(hi, 1e-12)
    return float(lo), float(hi)


def run(popseries: pd.DataFrame, train_until: int, horizons: list[int]) -> dict:
    ycols = sorted([c for c in popseries.columns if c.startswith("y") and c[1:].isdigit()], key=lambda c: int(c[1:]))
    years = np.array([int(c[1:]) for c in ycols])
    if len(years) < 10:
        return {"status": "unavailable", "reason": f"only {len(years)} yearly columns; need at least 10"}
    Y = popseries[ycols].to_numpy(float)
    last = int(years[-1])
    bt = backtest(Y, years, train_until)
    m = choose(bt)
    origins = [o for o in range(int(years[0]) + 8, last - 1) if o <= last - 2]
    env = envelope(Y, years, m, origins, 15)
    fut = np.arange(last + 1, max(horizons) + 1)
    P = predict(m, Y, years, fut)
    city_hist = Y.sum(axis=0)
    series = [{"year": int(y), "kind": "history", "total": float(t)} for y, t in zip(years, city_hist)]
    for i, y in enumerate(fut):
        p = float(P[:, i].sum())
        lo_e, hi_e = band(env, int(y - last))
        # error = (pred - actual)/actual  =>  actual in [pred/(1+hi_e), pred/(1+lo_e)]
        series.append({"year": int(y), "kind": "forecast", "total": p, "low": p / (1 + hi_e), "high": p / (1 + lo_e)})
    cells = pd.DataFrame({"h3": popseries["h3"], f"pop_{last}_series": Y[:, -1]})
    for h in horizons:
        cells[f"pop_{h}"] = P[:, int(h - last) - 1]
    big = max(horizons)
    cells[f"pop_growth_{big}"] = cells[f"pop_{big}"] - cells[f"pop_{last}_series"]
    return {"status": "ok", "method": m, "last_observed_year": last, "backtest": bt,
            "selection_rule": "lowest backtest WAPE; a method must beat the simpler ones by at least 1% to replace them",
            "envelope": {"observed_relative_error_by_horizon": {str(k): v for k, v in env["observed"].items()},
                         "growth_beyond_tested_per_year": env["per_year_growth"]},
            "city_series": series, "horizons": horizons,
            "caveats": ["History is WorldPop's modelled yearly series, not census counts.",
                        "Band = backtest error envelope across forecast origins, not a statistical interval; beyond the tested horizon it is extended linearly.",
                        "Policy shocks (new transit, master-plan changes) are not modelled."],
            "_cells": cells}
