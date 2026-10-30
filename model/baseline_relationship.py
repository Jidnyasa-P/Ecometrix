"""M3 baseline analysis: how strongly does surface temperature track greenness across the selected city's hexagons?

This is DESCRIPTIVE statistics on real data, not the heat-greenery model (that is Milestone M4). It also
sets the simple baseline that the M4 machine-learning model must beat:

  * ordinary least squares: LST ~ NDVI
  * evaluated with spatial block cross-validation (whole neighbourhoods held out, never random cells)
  * compared with a mean-only predictor

Run:  python model/baseline_relationship.py            (reads data/outputs/cells.parquet)
"""
from __future__ import annotations
import json
import sys
import argparse
from pathlib import Path
import numpy as np
import pandas as pd
import h3

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "pipelines"))
from ecometrix_pipeline.config import load_config

BLOCK_RES = 6          # H3 resolution used to define spatial blocks (about 36 km2 each)


def _ols(x: np.ndarray, y: np.ndarray):
    X = np.column_stack([np.ones_like(x), x])
    beta, *_ = np.linalg.lstsq(X, y, rcond=None)
    return beta


def _spearman(a: np.ndarray, b: np.ndarray) -> float:
    ra = pd.Series(a).rank().to_numpy()
    rb = pd.Series(b).rank().to_numpy()
    return float(np.corrcoef(ra, rb)[0, 1])


def compute_relationship(df: pd.DataFrame, block_res: int = BLOCK_RES, min_cells: int = 30) -> dict:
    need = {"h3", "ndvi", "lst_c"}
    if not need <= set(df.columns):
        return {"status": "unavailable", "reason": f"missing columns: {sorted(need - set(df.columns))}"}
    d = df[["h3", "ndvi", "lst_c"]].dropna()
    if len(d) < min_cells:
        return {"status": "unavailable", "reason": f"only {len(d)} cells with both NDVI and LST"}
    x, y = d["ndvi"].to_numpy(float), d["lst_c"].to_numpy(float)
    beta = _ols(x, y)
    pred = beta[0] + beta[1] * x
    ss_res, ss_tot = float(((y - pred) ** 2).sum()), float(((y - y.mean()) ** 2).sum())
    blocks = d["h3"].map(lambda c: h3.cell_to_parent(c, block_res)).to_numpy()
    ub = np.unique(blocks)
    se_model = se_mean = 0.0
    n_eval = 0
    if len(ub) >= 3:
        for b in ub:
            te = blocks == b
            tr = ~te
            if tr.sum() < 10 or te.sum() == 0:
                continue
            bt = _ols(x[tr], y[tr])
            se_model += float(((y[te] - (bt[0] + bt[1] * x[te])) ** 2).sum())
            se_mean += float(((y[te] - y[tr].mean()) ** 2).sum())
            n_eval += int(te.sum())
    cv = None
    if n_eval:
        rm, rb = (se_model / n_eval) ** 0.5, (se_mean / n_eval) ** 0.5
        cv = {"blocks": int(len(ub)), "cells_evaluated": n_eval, "rmse_ndvi_model_c": round(rm, 3),
              "rmse_mean_only_c": round(rb, 3), "rmse_improvement_pct": round(100 * (rb - rm) / rb, 1) if rb > 0 else None}
    return {"status": "ok", "n_cells": int(len(d)),
            "pearson_r": round(float(np.corrcoef(x, y)[0, 1]), 3), "spearman_rho": round(_spearman(x, y), 3),
            "slope_c_per_0p1_ndvi": round(float(beta[1] * 0.1), 3), "intercept_c": round(float(beta[0]), 2),
            "r2_in_sample": round(1 - ss_res / ss_tot, 3) if ss_tot > 0 else None, "spatial_block_cv": cv,
            "interpretation": "Association between cell-level greenness and surface temperature. It is not proof that adding "
                              "greenery causes this much cooling; the M4 model and its checks address that more carefully.",
            "caveat": "LST is a mid-morning surface-temperature snapshot, not air temperature."}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", nargs="?", help="Optional data directory (legacy positional form)")
    parser.add_argument("--city", default=None, help="City slug from config/registry.yaml")
    parser.add_argument("--config", default=None, help="Explicit city configuration YAML")
    args = parser.parse_args(argv)
    cfg = load_config(args.config, city=args.city)
    data = Path(args.output or cfg["data_output"])
    if not (data / "cells.parquet").exists():
        raise FileNotFoundError(f"Pipeline output not found: {data / 'cells.parquet'}. Run the data pipeline for {cfg['city']} first.")
    df = pd.read_parquet(data / "cells.parquet")
    res = compute_relationship(df)
    (data / "relationship.json").write_text(json.dumps(res, indent=2), encoding="utf-8")
    print(json.dumps(res, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
