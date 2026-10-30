"""M8: one-at-a-time sensitivity (tornado) analysis. Each ranged assumption is moved to its low and high value while all others stay at base,
for a representative site of each type (the site with the median present-value cost). Shows which assumptions drive cost and carbon,
so the weakest and most influential ones can be researched first."""
from __future__ import annotations
import copy
import sys
from pathlib import Path
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
from app.engine import scenario as S  # noqa: E402

TYPE_SECTIONS = {"mini_forest": ["common", "mini_forest"], "pocket_park": ["common", "pocket_park"]}


def _ranged(a: dict, sections: list[str]):
    for sec in sections:
        for k, v in a[sec].items():
            if isinstance(v, dict) and {"low", "base", "high"} <= set(v) and v["low"] != v["high"]:
                yield sec, k, v


def _metrics(r: dict) -> dict:
    out = {"cost_pv_inr": r["cost"]["present_value_inr"]["p50"]}
    c = r["benefits"]["carbon"]
    if c["available"]:
        out["carbon_t_co2e"] = c["t_co2e"]["p50"]
        out["inr_per_t_co2e"] = r["cost_effectiveness"].get("inr_per_t_co2e", {}).get("p50") if r["cost_effectiveness"].get("inr_per_t_co2e") else None
    if r["cost_effectiveness"].get("inr_per_person_newly_served"):
        out["inr_per_person_newly_served"] = r["cost_effectiveness"]["inr_per_person_newly_served"]["p50"]
    return out


def representative(sites: pd.DataFrame, assumptions: dict, t: str) -> dict | None:
    sub = sites[sites["type"] == t]
    if sub.empty:
        return None
    costs = []
    for i in range(len(sub)):
        row = {k: (None if isinstance(v, float) and not np.isfinite(v) else v) for k, v in sub.iloc[i].to_dict().items()}
        costs.append(S.run(row, assumptions, mode="base")["cost"]["present_value_inr"]["p50"])
    i = int(np.argsort(costs)[len(costs) // 2])
    return {k: (None if isinstance(v, float) and not np.isfinite(v) else v) for k, v in sub.iloc[i].to_dict().items()}


def tornado(site: dict, assumptions: dict) -> dict:
    t = site["type"]
    base = _metrics(S.run(site, assumptions, mode="base"))
    rows = []
    for sec, k, v in _ranged(assumptions, TYPE_SECTIONS[t]):
        eff = {}
        for end in ("low", "high"):
            a = copy.deepcopy(assumptions)
            a[sec][k]["base"] = v[end]
            eff[end] = _metrics(S.run(site, a, mode="base"))
        rows.append({"parameter": f"{sec}.{k}", "low": v["low"], "base": v["base"], "high": v["high"], "unit": v.get("unit"),
                     "effects": {m: {"at_low": eff["low"].get(m), "at_high": eff["high"].get(m)} for m in base}})
    for H in (5, 15):                                                         # horizon is a choice, not a range, but it matters
        e = _metrics(S.run(site, assumptions, horizon_years=H, mode="base"))
        rows.append({"parameter": f"horizon_years = {H}", "low": None, "base": None, "high": None, "unit": "years",
                     "effects": {m: {"at_low": e.get(m), "at_high": e.get(m)} for m in base}, "variant": True})
    cool = site.get("dlst_p50")
    if cool is not None and np.isfinite(cool):
        pass
    for r in rows:
        swing = []
        for m, v in r["effects"].items():
            a, b = v["at_low"], v["at_high"]
            if a is not None and b is not None and base[m]:
                swing.append(abs(b - a) / abs(base[m]))
        r["max_relative_swing"] = float(max(swing)) if swing else 0.0
    rows.sort(key=lambda r: -r["max_relative_swing"])
    return {"site_id": site["site_id"], "type": t, "area_ha": site["area_ha"], "base": base, "rows": rows}


def run(sites: pd.DataFrame, assumptions: dict) -> dict:
    out = {}
    for t in TYPE_SECTIONS:
        rep = representative(sites, assumptions, t)
        if rep:
            out[t] = tornado(rep, assumptions)
    return {"status": "ok" if out else "unavailable", "method": "one at a time, others at base, median-cost site of each type", "types": out}
