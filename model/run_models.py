"""Run the analytical modules on the pipeline outputs.

    python model/run_models.py [data/outputs]

Reads cells.parquet and popseries.parquet; writes heat_model.json, forecast.json, need_report.json, analysis.parquet,
sites.parquet and models_manifest.json. Each module is independent: if one cannot run, the reason is recorded and shown in the app.
"""
from __future__ import annotations
import json
import os
import sys
import traceback
from pathlib import Path
import numpy as np
import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
import heat_model, forecast, need_score, sites, portfolio, sensitivity  # noqa: E402


def _clean(o):
    if isinstance(o, dict): return {str(k): _clean(v) for k, v in o.items() if not str(k).startswith("_")}
    if isinstance(o, (list, tuple)): return [_clean(v) for v in o]
    if isinstance(o, np.ndarray): return _clean(o.tolist())
    if isinstance(o, (np.integer,)): return int(o)
    if isinstance(o, (np.floating, float)): return float(o) if np.isfinite(o) else None
    return o


def _dump(path: Path, obj):
    path.write_text(json.dumps(_clean(obj), indent=2, allow_nan=False), encoding="utf-8")


def main(argv=None) -> int:
    argv = argv or sys.argv[1:]
    out = Path(argv[0]) if argv else ROOT / "data" / "outputs"
    cfg = yaml.safe_load(Path(os.environ.get("ECOMETRIX_CONFIG") or ROOT / "config" / "pilot_pune.yaml").read_text(encoding="utf-8"))
    cells = pd.read_parquet(out / "cells.parquet")
    status: dict[str, dict] = {}

    def step(name, fn):
        try:
            r = fn()
            status[name] = {"status": "ok"}
            return r
        except Exception as e:
            traceback.print_exc()
            status[name] = {"status": "failed", "reason": f"{type(e).__name__}: {e}"}
            return None

    heat = step("heat_model", lambda: heat_model.run(cells))
    if heat is not None and heat.get("status") != "ok":
        status["heat_model"] = {"status": "failed", "reason": heat.get("reason", "unavailable")}
        _dump(out / "heat_model.json", {"status": "unavailable", "reason": heat.get("reason")})
        heat = None
    targets = step("greenness_targets", lambda: heat_model.greenness_targets(cells)) or {}
    if heat is not None:
        _dump(out / "heat_model.json", {**heat, "greenness_targets": targets})

    fc_cells, growth_col = None, None
    ps_path = out / "popseries.parquet"
    if ps_path.exists():
        fres = step("forecast", lambda: forecast.run(pd.read_parquet(ps_path), cfg["forecast"]["train_until"], cfg["forecast"]["horizons"]))
        if fres is not None and fres.get("status") == "ok":
            _dump(out / "forecast.json", fres)
            fc_cells, growth_col = fres["_cells"], f"pop_growth_{max(cfg['forecast']['horizons'])}"
        elif fres is not None:
            status["forecast"] = {"status": "failed", "reason": fres.get("reason", "unavailable")}
    else:
        status["forecast"] = {"status": "failed", "reason": "popseries.parquet not found: the yearly population layer failed or was not built"}

    need_df = step("need_score", lambda: need_score.components(cells, fc_cells, growth_col))
    analysis = None
    if need_df is not None:
        presets = cfg["need"]["presets"]
        need_df["need_balanced"] = need_score.score(need_df, presets["balanced"])
        need_df["need_no_regret"] = need_score.no_regret_flags(need_df, presets)
        stab = need_score.stability(need_df, presets)
        _dump(out / "need_report.json", {"presets": presets, "components_used": need_score.available(need_df), "stability": stab,
                                         "excluded": "Residents' vulnerability (age, income, health) is not included: no open data was built for it."})
        analysis = need_df
        if fc_cells is not None:
            big = max(cfg["forecast"]["horizons"])
            a = fc_cells.drop(columns=[c for c in fc_cells.columns if c.startswith("pop_") and c.endswith("_series")] + [], errors="ignore")
            analysis = analysis.merge(fc_cells, on="h3", how="left")
            if "access_share" in cells:
                acc = cells[["h3", "access_share"]]
                analysis = analysis.merge(acc, on="h3", how="left")
                analysis[f"pop_unserved_{big}"] = analysis[f"pop_{big}"] * (1.0 - analysis["access_share"])
                analysis = analysis.drop(columns=["access_share"])
        analysis.to_parquet(out / "analysis.parquet", index=False)

    if analysis is not None:
        s = step("sites", lambda: sites.build(cells, analysis, heat, targets, cfg["candidates"]))
        if s is not None:
            if s.empty:
                status["sites"] = {"status": "failed", "reason": "no hexagon met the candidate rules (open land and residents)"}
            else:
                s.to_parquet(out / "sites.parquet", index=False)
                status["sites"]["count"] = int(len(s))
                status["sites"]["by_type"] = s["type"].value_counts().to_dict()
    sp = out / "sites.parquet"
    if sp.exists():
        from app.engine import params as eparams
        A = eparams.load(ROOT / "config" / "assumptions.yaml")
        sdf = pd.read_parquet(sp)
        step("sensitivity", lambda: _dump(out / "sensitivity.json", sensitivity.run(sdf, A)))
        pix = out / "site_pixels.parquet"
        if not pix.exists():
            status["portfolio"] = {"status": "failed", "reason": "site_pixels.parquet not found: exact catchments need the population layer; portfolios are not computed without them (no double-counting shortcuts)"}
        else:
            def _port():
                inst = portfolio.build_instance(sdf, pd.read_parquet(pix), A, rings=cfg["portfolio"].get("min_separation_rings", 0))
                g = portfolio.run_grid(inst, sdf, A, cfg, time_limit=cfg["portfolio"].get("solver_time_limit_s", 90))
                _dump(out / "portfolios.json", g)
                return g
            g = step("portfolio", _port)
            if g is not None:
                status["portfolio"]["solutions"] = len(g["results"])
    _dump(out / "models_manifest.json", {"modules": status})
    print({k: v["status"] for k, v in status.items()})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
