"""M5: the need score. 0 to 100, built from four visible components, each a percentile rank (0 to 1) across populated hexagons:

  heat    surface temperature (hotter = higher)
  people  residents today (more = higher)
  gap     share of residents NOT within 300 m of a qualifying park (less access = higher)
  growth  forecast population growth to 2035 (more people added = higher)

The weights are POLICY CHOICES, not facts, so they are presets the user can see and change. Hexagons with no modelled residents get no score.
Not included, because no open data exists for it here: vulnerability of residents (age, income, health).
"""
from __future__ import annotations
import numpy as np
import pandas as pd

COMPONENTS = ["heat", "people", "gap", "growth"]


def _rank(s: pd.Series) -> pd.Series:
    return s.rank(pct=True, method="average")


def components(cells: pd.DataFrame, fc_cells: pd.DataFrame | None, growth_col: str | None) -> pd.DataFrame:
    df = pd.DataFrame({"h3": cells["h3"]})
    populated = cells["pop"] > 0 if "pop" in cells else pd.Series(False, index=cells.index)
    src = {
        "heat": cells["lst_c"] if "lst_c" in cells else None,
        "people": cells["pop"] if "pop" in cells else None,
        "gap": (1.0 - cells["access_share"]) if "access_share" in cells else None,
    }
    if fc_cells is not None and growth_col in fc_cells:
        src["growth"] = cells[["h3"]].merge(fc_cells[["h3", growth_col]], on="h3", how="left")[growth_col]
    for name in COMPONENTS:
        s = src.get(name)
        if s is None:
            continue
        s = pd.Series(np.asarray(s, float), index=cells.index).where(populated)
        df[f"need_{name}"] = _rank(s)
    return df


def available(df: pd.DataFrame) -> list[str]:
    return [c for c in COMPONENTS if f"need_{c}" in df.columns]


def score(df: pd.DataFrame, weights: dict[str, float]) -> pd.Series:
    """Weights are renormalised over the components that exist; a hexagon needs every available component to be scored."""
    comps = [c for c in available(df) if weights.get(c, 0) > 0]
    if not comps:
        return pd.Series(np.nan, index=df.index)
    w = np.array([weights[c] for c in comps], float)
    w = w / w.sum()
    M = df[[f"need_{c}" for c in comps]].to_numpy(float)
    s = 100.0 * (M * w).sum(axis=1)
    s[np.isnan(M).any(axis=1)] = np.nan
    return pd.Series(s, index=df.index)


def stability(df: pd.DataFrame, presets: dict[str, dict[str, float]], top_frac: float = 0.10) -> dict:
    """How much do the rankings depend on the (policy) weights? Spearman correlation and top-decile overlap between presets."""
    scores = {k: score(df, w) for k, w in presets.items()}
    names = list(scores)
    ok = pd.concat(scores, axis=1).dropna()
    if len(ok) < 20:
        return {"status": "unavailable", "reason": f"only {len(ok)} scored hexagons"}
    k = max(1, int(len(ok) * top_frac))
    tops = {n: set(ok[n].nlargest(k).index) for n in names}
    pairs = []
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            rho = float(ok[a].rank().corr(ok[b].rank()))
            inter = len(tops[a] & tops[b])
            pairs.append({"a": a, "b": b, "spearman": round(rho, 3), "top_decile_overlap_pct": round(100 * inter / k, 1)})
    always = set.intersection(*tops.values())
    return {"status": "ok", "scored_cells": int(len(ok)), "top_fraction": top_frac, "pairs": pairs,
            "no_regret_cells": len(always), "no_regret_share_of_top_pct": round(100 * len(always) / k, 1),
            "components_used": available(df)}


def no_regret_flags(df: pd.DataFrame, presets: dict, top_frac: float = 0.10) -> pd.Series:
    scores = pd.concat({k: score(df, w) for k, w in presets.items()}, axis=1)
    ok = scores.dropna()
    flag = pd.Series(0, index=df.index, dtype="int8")
    if len(ok) < 20:
        return flag
    k = max(1, int(len(ok) * top_frac))
    always = set.intersection(*[set(ok[c].nlargest(k).index) for c in ok.columns])
    flag.loc[list(always)] = 1
    return flag
