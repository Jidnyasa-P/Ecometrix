"""M6: the portfolio optimiser. Chooses the set of candidate sites that does the most good within a budget.

Exact method: integer programming (Google OR-Tools CP-SAT), not a heuristic, so on small cases the answer is PROVEN equal to brute force.

What is decided   which candidate sites to fund (each at its default area), at most one per hexagon (and optionally a gap of rings between sites).
Objective         weighted sum of three NORMALISED benefits (each divided by the best any single site achieves):
                    cooling       person-degrees of modelled surface cooling (adds up across sites; no spill-over is credited)
                    people        residents newly within 300 m of a park, counted ONCE however many chosen sites reach them (pixel-exact)
                    carbon        tonnes CO2e stored (mini-forests only)
Constraints       budget on the median present-value cost; optional EQUITY rule (at least a share of spend in the top third of need);
                  one site per hexagon (plus optional separation).
Uncertainty       after the choice, each site's cost and benefits are re-drawn (Monte Carlo, fixed seed) and added up.
Weights and shares are POLICY CHOICES, listed in config/pilot_pune.yaml and shown in the app.
"""
from __future__ import annotations
import itertools
import sys
from dataclasses import dataclass, field
from pathlib import Path
import h3
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
from app.engine import scenario as S  # noqa: E402

SCALE = 1_000_000


@dataclass
class Instance:
    site_ids: list
    hexes: list
    types: list
    cost: np.ndarray               # median present-value cost, INR
    cooling: np.ndarray            # person-degrees (median), 0 when unavailable
    carbon: np.ndarray             # t CO2e (median), 0 when not applicable
    high_need: np.ndarray          # bool
    pixels: list                   # per site: np.ndarray of pixel ids it newly serves (empty if it does not count for access)
    pixel_people: dict = field(default_factory=dict)   # pixel id -> people
    conflicts: list = field(default_factory=list)      # (i, j) pairs that may not both be chosen
    need: np.ndarray | None = None

    @property
    def n(self) -> int: return len(self.site_ids)


def conflicts_for(hexes: list, rings: int = 0) -> list:
    """Pairs of sites that cannot both be chosen: same hexagon, or within `rings` hexagon rings of each other."""
    by_hex: dict[str, list[int]] = {}
    for i, h in enumerate(hexes):
        by_hex.setdefault(h, []).append(i)
    pairs = set()
    for h, idxs in by_hex.items():
        for a, b in itertools.combinations(idxs, 2):
            pairs.add((a, b))
        if rings > 0:
            for nb in h3.grid_disk(h, rings):
                if nb != h and nb in by_hex:
                    for a in idxs:
                        for b in by_hex[nb]:
                            pairs.add((min(a, b), max(a, b)))
    return sorted(pairs)


def refs(inst: Instance) -> dict:
    people_each = np.array([sum(inst.pixel_people[p] for p in px) for px in inst.pixels]) if inst.n else np.array([])
    f = lambda a: float(a.max()) if a.size and a.max() > 0 else 1.0
    return {"cooling": f(inst.cooling), "carbon": f(inst.carbon), "people": f(people_each)}


def _coeffs(inst: Instance, w: dict, r: dict):
    site = [round(SCALE * (w["cooling"] * inst.cooling[i] / r["cooling"] + w["carbon"] * inst.carbon[i] / r["carbon"])) for i in range(inst.n)]
    pix = {p: round(SCALE * w["people"] * inst.pixel_people[p] / r["people"]) for px in inst.pixels for p in px}
    return site, pix


def objective_value(inst: Instance, chosen, w: dict, r: dict) -> int:
    site, pix = _coeffs(inst, w, r)
    covered = set(p for i in chosen for p in inst.pixels[i])
    return int(sum(site[i] for i in chosen) + sum(pix[p] for p in covered))


def feasible(inst: Instance, chosen, budget: float, equity_pct: int) -> bool:
    chosen = list(chosen)
    cs = set(chosen)
    if sum(round(inst.cost[i]) for i in chosen) > round(budget):
        return False
    if any(a in cs and b in cs for a, b in inst.conflicts):
        return False
    if equity_pct > 0 and sum(round(inst.cost[i]) * (100 * int(inst.high_need[i]) - equity_pct) for i in chosen) < 0:
        return False
    return True


def brute_force(inst: Instance, budget: float, w: dict, equity_pct: int = 0) -> tuple[int, tuple]:
    """Reference answer by trying every subset. Only for tiny instances (tests)."""
    r = refs(inst)
    best, best_set = -1, ()
    for k in range(inst.n + 1):
        for c in itertools.combinations(range(inst.n), k):
            if feasible(inst, c, budget, equity_pct):
                v = objective_value(inst, c, w, r)
                if v > best:
                    best, best_set = v, c
    return best, best_set


def solve(inst: Instance, budget: float, w: dict, equity_pct: int = 0, time_limit: float = 90.0, rel_gap: float = 0.002,
          max_candidates: int | None = 3000, seed: int = 1, workers: int = 1) -> dict:
    from ortools.sat.python import cp_model
    r = refs(inst)
    site_c, pix_c = _coeffs(inst, w, r)
    keep = list(range(inst.n))
    prefiltered = False
    if max_candidates and inst.n > max_candidates:
        score = np.array([(site_c[i] + sum(pix_c[p] for p in inst.pixels[i])) / max(inst.cost[i], 1.0) for i in range(inst.n)])
        keep = sorted(np.argsort(-score)[:max_candidates].tolist())
        prefiltered = True
    pos = {i: k for k, i in enumerate(keep)}
    m = cp_model.CpModel()
    x = {i: m.NewBoolVar(f"x{i}") for i in keep}
    m.Add(sum(round(inst.cost[i]) * x[i] for i in keep) <= round(budget))
    for a, b in inst.conflicts:
        if a in pos and b in pos:
            m.Add(x[a] + x[b] <= 1)
    if equity_pct > 0:
        m.Add(sum(round(inst.cost[i]) * (100 * int(inst.high_need[i]) - equity_pct) * x[i] for i in keep) >= 0)
    covers: dict[int, list] = {}
    for i in keep:
        for p in inst.pixels[i]:
            covers.setdefault(p, []).append(i)
    y = {}
    for p, sites in covers.items():
        if pix_c.get(p, 0) <= 0:
            continue
        y[p] = m.NewBoolVar(f"y{p}")
        m.Add(y[p] <= sum(x[i] for i in sites))
    m.Maximize(sum(site_c[i] * x[i] for i in keep) + sum(pix_c[p] * y[p] for p in y))
    s = cp_model.CpSolver()
    s.parameters.max_time_in_seconds = float(time_limit)
    s.parameters.relative_gap_limit = float(rel_gap)
    s.parameters.num_workers = int(workers)
    s.parameters.random_seed = int(seed)
    st = s.Solve(m)
    name = s.StatusName(st)
    if name not in ("OPTIMAL", "FEASIBLE"):
        return {"status": name, "chosen": [], "objective": 0, "bound": 0, "gap": None, "prefiltered": prefiltered, "candidates": len(keep)}
    chosen = [i for i in keep if s.Value(x[i])]
    obj, bound = s.ObjectiveValue(), s.BestObjectiveBound()
    return {"status": name, "chosen": chosen, "objective": int(round(obj)), "bound": float(bound),
            "gap": float((bound - obj) / max(bound, 1.0)) if name == "FEASIBLE" else 0.0, "prefiltered": prefiltered, "candidates": len(keep)}


def greedy_by_need(inst: Instance, budget: float, equity_pct: int = 0) -> list:
    """The simple baseline a planner might use: fund sites in order of need score while the budget lasts."""
    order = np.argsort(-(inst.need if inst.need is not None else np.zeros(inst.n)), kind="stable")
    chosen, spent = [], 0
    for i in order:
        c = round(inst.cost[i])
        if spent + c <= round(budget) and feasible(inst, chosen + [int(i)], 10 ** 18, 0):
            chosen.append(int(i)); spent += c
    return chosen


def evaluate(inst: Instance, chosen, sites: pd.DataFrame, assumptions: dict, budget: float, w: dict, draws: int = 1000, seed: int = 42,
             mode: str = "mc") -> dict:
    """Add up the chosen sites with uncertainty. People are counted once (pixel-exact); cost and benefits are summed Monte Carlo draws."""
    chosen = sorted(chosen)
    n = 1 if mode == "base" else draws
    cost = np.zeros(n); cool = np.zeros(n); carb = np.zeros(n); sites_out = []
    seen: dict[int, str] = {}
    for i in chosen:
        row = sites.iloc[i].to_dict()
        row = {k: (None if isinstance(v, float) and not np.isfinite(v) else v) for k, v in row.items()}
        r = S.run(row, assumptions, draws=draws, seed=seed + i, mode=mode, return_draws=True)
        d = r["_draws"]
        cost += d["cost"]
        if d["person_degrees"] is not None: cool += d["person_degrees"]
        if d["carbon"] is not None: carb += d["carbon"]
        marg = 0.0
        for p in inst.pixels[i]:
            if p not in seen:
                seen[p] = inst.site_ids[i]; marg += inst.pixel_people[p]
        sites_out.append({"site_id": inst.site_ids[i], "h3": inst.hexes[i], "type": inst.types[i], "area_ha": float(row["area_ha"]),
                          "cost_p50_inr": r["cost"]["present_value_inr"]["p50"], "cooling_person_degrees_p50": float(inst.cooling[i]),
                          "carbon_t_co2e_p50": float(inst.carbon[i]), "people_newly_served_marginal": marg, "high_need": bool(inst.high_need[i]),
                          "lat": float(row["lat"]), "lng": float(row["lng"])})
    q = lambda a: {"p10": float(np.percentile(a, 10)), "p50": float(np.percentile(a, 50)), "p90": float(np.percentile(a, 90))}
    people = float(sum(inst.pixel_people[p] for p in seen))
    spend = sum(inst.cost[i] for i in chosen)
    eq = float(sum(inst.cost[i] for i in chosen if inst.high_need[i]) / spend) if spend > 0 else 0.0
    rr = refs(inst)
    norm = (w["cooling"] * float(sum(inst.cooling[i] for i in chosen)) / rr["cooling"] + w["carbon"] * float(sum(inst.carbon[i] for i in chosen)) / rr["carbon"]
            + w["people"] * people / rr["people"])
    return {"n_sites": len(chosen), "by_type": {t: int(sum(1 for i in chosen if inst.types[i] == t)) for t in sorted(set(inst.types))},
            "cost_pv_inr": q(cost), "cooling_person_degrees": q(cool), "carbon_t_co2e": q(carb), "people_newly_served": people,
            "prob_within_budget": float(np.mean(cost <= budget)), "high_need_share_of_spend": eq, "objective_norm": float(norm), "sites": sites_out}


def build_instance(sites: pd.DataFrame, site_pixels: pd.DataFrame, assumptions: dict, rings: int = 0) -> Instance:
    """Per-site median cost and benefits come from the SAME engine the scenario runner uses (base mode), so the two always agree."""
    cost, cool, carb, access = [], [], [], []
    for i in range(len(sites)):
        row = {k: (None if isinstance(v, float) and not np.isfinite(v) else v) for k, v in sites.iloc[i].to_dict().items()}
        r = S.run(row, assumptions, mode="base")
        cost.append(r["cost"]["present_value_inr"]["p50"])
        c = r["benefits"]["cooling"]
        cool.append(c["person_degrees"]["p50"] if c["available"] else 0.0)
        k = r["benefits"]["carbon"]
        carb.append(k["t_co2e"]["p50"] if k["available"] else 0.0)
        access.append(r["benefits"]["people_newly_served"]["value"] > 0)
    by_hex = {h: g for h, g in site_pixels.groupby("h3")} if len(site_pixels) else {}
    pixels, pp = [], {}
    for i in range(len(sites)):
        px = np.array([], dtype=int)
        if access[i] and sites["h3"].iloc[i] in by_hex:
            g = by_hex[sites["h3"].iloc[i]]
            px = g["pixel"].to_numpy(int)
            for p, v in zip(px, g["people"].to_numpy(float)):
                pp[int(p)] = float(v)
        pixels.append(px)
    need = sites["need_balanced"].to_numpy(float) if "need_balanced" in sites else np.zeros(len(sites))
    thr = float(np.nanpercentile(need, 100 * 2 / 3)) if np.isfinite(need).any() else 0.0
    inst = Instance(site_ids=sites["site_id"].tolist(), hexes=sites["h3"].tolist(), types=sites["type"].tolist(), cost=np.array(cost), cooling=np.array(cool),
                    carbon=np.array(carb), high_need=np.nan_to_num(need, nan=-1) >= thr, pixels=pixels, pixel_people=pp, need=np.nan_to_num(need, nan=-1))
    inst.conflicts = conflicts_for(inst.hexes, rings)
    return inst


def run_grid(inst: Instance, sites: pd.DataFrame, assumptions: dict, cfg: dict, time_limit: float = 90.0, draws: int = 1000) -> dict:
    pc = cfg["portfolio"]
    total = float(inst.cost.sum())
    med = float(np.median(inst.cost)) if inst.n else 0.0
    budgets = [round(m * med, -5) for m in pc["budget_multiples_of_median_site_cost"] if m * med < 0.6 * total]
    results = []
    for preset, w in pc["presets"].items():
        for b in budgets:
            for eq in pc["equity_shares_pct"]:
                sol = solve(inst, b, w, eq, time_limit=time_limit)
                ev = evaluate(inst, sol["chosen"], sites, assumptions, b, w, draws=draws)
                base_sel = greedy_by_need(inst, b)
                bev = evaluate(inst, base_sel, sites, assumptions, b, w, draws=200)
                gain = 100 * (ev["objective_norm"] - bev["objective_norm"]) / bev["objective_norm"] if bev["objective_norm"] > 0 else None
                results.append({"preset": preset, "budget_inr": b, "equity_pct": eq, "solver": {k: sol[k] for k in ("status", "gap", "prefiltered", "candidates")},
                                **ev, "baseline_top_need": {k: bev[k] for k in ("n_sites", "people_newly_served", "cost_pv_inr", "cooling_person_degrees", "carbon_t_co2e", "objective_norm")},
                                "gain_vs_top_need_pct": gain})
    freq: dict[str, int] = {}
    pool = [r for r in results if r["equity_pct"] == 0 and r["budget_inr"] >= (budgets[len(budgets) // 2] if budgets else 0)]
    for r in pool:
        for s in r["sites"]:
            freq[s["site_id"]] = freq.get(s["site_id"], 0) + 1
    thr = pc.get("no_regret_min_share", 0.75) * max(len(pool), 1)
    return {"status": "ok", "presets": pc["presets"], "budgets_inr": budgets, "equity_shares_pct": pc["equity_shares_pct"],
            "references": refs(inst), "median_site_cost_inr": med, "candidate_sites": inst.n,
            "no_regret_site_ids": sorted(k for k, v in freq.items() if v >= thr), "no_regret_rule": f"chosen in at least {int(pc.get('no_regret_min_share', 0.75) * 100)}% of the solutions with no equity rule and a budget at or above the middle of the grid",
            "high_need_rule": "top third of candidate sites by the balanced need score",
            "normalisation": "each benefit is divided by the best any single site achieves, then weighted",
            "results": results}
