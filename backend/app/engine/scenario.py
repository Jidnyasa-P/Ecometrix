"""Impact and cost engine for ONE site (Milestone M4/M5). Plain arithmetic, no black box.

Costs are present values (PV) in rupees. Benefits are kept as separate indicators and never merged into one money figure.
Every result is compared with doing nothing, and every number carries an evidence label.

What this deliberately does not do:
  * no ROI or payback (green space earns no revenue in this model)
  * no carbon for pocket parks (no Indian measurement was found)
  * no cooling spill-over to neighbouring hexagons (conservative; footprint hexagon only)
  * people served is NOT summed across sites: overlapping catchments are handled when a portfolio is optimised (Milestone M6)
"""
from __future__ import annotations
import numpy as np
from . import params as P

TYPES = ("pocket_park", "mini_forest")


def _q(a: np.ndarray) -> dict:
    return {"p10": float(np.percentile(a, 10)), "p50": float(np.percentile(a, 50)), "p90": float(np.percentile(a, 90))}


def _disc(r: np.ndarray, t: np.ndarray) -> np.ndarray:
    """Discount factors, shape (draws, len(t)) for years t."""
    return (1.0 + r)[:, None] ** (-t[None, :])


def run(site: dict, assumptions: dict, area_ha: float | None = None, horizon_years: int | None = None,
        budget_inr: float | None = None, draws: int = 2000, seed: int = 42, mode: str = "mc") -> dict:
    t = site["type"]
    if t not in TYPES:
        raise ValueError(f"unknown intervention type {t}")
    max_ha = float(site["area_ha"])
    area = max_ha if area_ha is None else float(area_ha)
    if not (0 < area <= max_ha + 1e-9):
        raise ValueError(f"area must be above 0 and at most {max_ha:.2f} ha (the open land estimated for this site)")
    H = int(horizon_years or P.value(assumptions["common"]["horizon_years"]))
    n = 1 if mode == "base" else int(draws)
    rng = np.random.default_rng(seed)
    a = assumptions
    r = P.draw(a["common"]["discount_rate"], rng, n, mode)
    m2 = area * 10_000.0
    yrs = np.arange(1, H + 1, dtype=float)
    df = _disc(r, yrs)

    # ---- cost (present value)
    if t == "mini_forest":
        mf = a["mini_forest"]
        capex = m2 * P.draw(mf["capex_inr_per_m2"], rng, n, mode)
        sap_n = m2 * P.draw(mf["saplings_per_m2"], rng, n, mode)
        repl = sap_n * (1.0 - P.draw(mf["sapling_survival"], rng, n, mode)) * P.draw(mf["sapling_cost_inr"], rng, n, mode) / (1.0 + r)
        E = min(int(P.value(mf["establishment_years"])), H)
        maint_y = m2 * P.draw(mf["maintenance_inr_per_m2_yr"], rng, n, mode)
        maint = maint_y * df[:, :E].sum(axis=1)
        pv = capex + repl + maint
        parts = {"capital": capex, "replacing_failed_saplings": repl, "establishment_maintenance": maint}
        basis = "Capital cost plus replacement of failed saplings plus maintenance for the establishment years only. Later upkeep is not included."
    else:
        pk = a["pocket_park"]
        annual = m2 * P.draw(pk["annual_all_in_cost_inr_per_m2"], rng, n, mode)
        pv = annual * df.sum(axis=1)
        parts = {"annual_all_in_cost_over_horizon": pv}
        basis = "PMC's average all-in garden spend per m2 per year (development, plantation and maintenance), applied every year of the horizon."

    # ---- benefits
    cool = None
    p10, p50, p90 = site.get("dlst_p10"), site.get("dlst_p50"), site.get("dlst_p90")
    cool_note = ""
    if p50 is None or not np.isfinite(p50):
        cool_note = "No cooling estimate: the heat model or a data-derived greenness target was not available for this site."
    else:
        scale = area / max_ha                       # response assumed proportional to area (exact only at the default area)
        lo, mid, hi = float(p10) * scale, float(p50) * scale, float(p90) * scale
        d = np.full(n, mid) if (mode == "base" or hi == lo) else rng.triangular(min(lo, mid), mid, max(hi, mid), n)
        pop = float(site["pop"])
        cool = {"delta_lst_c": _q(d), "person_degrees": _q(-d * pop), "cell_population": pop}
        cool_note = ("Modelled change in surface temperature of the hexagon once the planting matures (about five years for a forest), "
                     "from the heat model. Surface temperature is not air temperature. Range is an approximation from bootstrap runs.")

    served = 0.0
    served_note = ""
    counts = bool(P.value(a[t]["counts_for_access"]))
    if t == "pocket_park":
        min_ha = float(P.value(a["pocket_park"]["min_area_ha_for_access"]))
        if area >= min_ha:
            served = float(site.get("pop_unserved_300m") or 0.0)
            served_note = "Residents within 300 m of the site who are not already within 300 m of a mapped park of at least 0.5 ha."
        else:
            served_note = f"A park smaller than {min_ha} ha does not count toward the WHO access measure."
    else:
        served_note = "Not counted: dense plantations are not assumed to be open to the public." if not counts else ""

    carbon = None
    carbon_note = ""
    if t == "mini_forest":
        mf = a["mini_forest"]
        rates = P.carbon_rates(mf["carbon_age_curve_mg_c_per_ha_yr"]["points"], H,
                               P.draw(mf["carbon_after_year5_factor"], rng, n, mode), P.draw(mf["carbon_scale"], rng, n, mode))
        co2 = rates.sum(axis=1) * area * float(P.value(a["common"]["co2_per_c"]))
        carbon = {"t_co2e": _q(co2)}
        carbon_note = "Carbon stored by new trees over the horizon, scaled from three measured Indian plots; ASSUMED ranges. Existing trees are the baseline, not a benefit."
    else:
        co2 = None
        carbon_note = a["pocket_park"]["carbon"]["source"]

    # ---- cost-effectiveness, each benefit separately
    ce = {}
    if served > 0:
        ce["inr_per_person_newly_served"] = _q(pv / served)
    if co2 is not None:
        with np.errstate(divide="ignore", invalid="ignore"):
            ratio = np.where(co2 > 0, pv / np.maximum(co2, 1e-9), np.nan)
        ce["inr_per_t_co2e"] = _q(ratio[np.isfinite(ratio)]) if np.isfinite(ratio).any() else None
    if cool is not None and cool["person_degrees"]["p50"] > 0:
        pdv = -d * float(site["pop"])
        ok = pdv > 0
        if ok.any():
            ce["inr_per_person_degree_c"] = _q(pv[ok] / pdv[ok])

    out = {
        "site_id": site["site_id"], "type": t, "area_ha": area, "max_area_ha": max_ha, "horizon_years": H,
        "draws": n, "mode": mode, "seed": seed,
        "baseline": "Compared with doing nothing at this site. Existing trees and parks are not counted as benefit.",
        "cost": {"present_value_inr": _q(pv), "breakdown_base_inr": {k: float(np.percentile(v, 50)) for k, v in parts.items()},
                 "basis": basis, "evidence": "ASSUMED"},
        "benefits": {
            "cooling": {**(cool or {}), "available": cool is not None, "evidence": "MODELLED", "note": cool_note},
            "people_newly_served": {"value": served, "evidence": "MODELLED", "note": served_note},
            "carbon": {**(carbon or {}), "available": carbon is not None, "evidence": "ASSUMED", "note": carbon_note},
        },
        "cost_effectiveness": ce,
        "label_note": "SIMULATED: none of this has been built. Costs and carbon are ASSUMED ranges; cooling and people are MODELLED.",
    }
    if budget_inr is not None:
        b = float(budget_inr)
        p50 = float(np.percentile(pv, 50))
        out["budget"] = {"budget_inr": b, "probability_within_budget": float(np.mean(pv <= b)), "p50_within_budget": p50 <= b,
                         "max_area_ha_at_p50_cost": float(min(max_ha, area * b / p50)) if p50 > 0 else None,
                         "note": "Cost scales linearly with area, so the largest affordable area is estimated from the median cost per hectare."}
    return out
