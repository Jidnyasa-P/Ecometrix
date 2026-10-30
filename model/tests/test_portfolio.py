import sys
from pathlib import Path
import h3
import numpy as np
import pandas as pd
import pytest
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import portfolio as pf
from app.engine import params as P, scenario as S

W = {"cooling": 0.34, "people": 0.33, "carbon": 0.33}
CENTRE = h3.latlng_to_cell(18.52, 73.85, 9)


def rand_inst(n=11, seed=0, rings=0, n_pix=14):
    rng = np.random.default_rng(seed)
    cells = sorted(h3.grid_disk(CENTRE, 2))
    hexes = [cells[int(rng.integers(0, 7))] for _ in range(n)]            # few hexagons: forces same-hexagon conflicts
    pix_people = {p: float(rng.integers(5, 60)) for p in range(n_pix)}
    pixels = [np.array(sorted(rng.choice(n_pix, size=int(rng.integers(2, 7)), replace=False))) if rng.random() < 0.6 else np.array([], dtype=int) for _ in range(n)]
    inst = pf.Instance(site_ids=[f"s{i}" for i in range(n)], hexes=hexes, types=["pocket_park" if len(p) else "mini_forest" for p in pixels],
                       cost=rng.integers(1, 6, n) * 1_000_000.0, cooling=rng.uniform(0, 100, n), carbon=np.where(rng.random(n) < 0.4, rng.uniform(10, 80, n), 0.0),
                       high_need=rng.random(n) < 0.4, pixels=pixels, pixel_people=pix_people, need=rng.uniform(0, 100, n))
    inst.conflicts = pf.conflicts_for(inst.hexes, rings)
    return inst


@pytest.mark.parametrize("seed", range(8))
@pytest.mark.parametrize("equity", [0, 50])
def test_solver_equals_brute_force(seed, equity):
    inst = rand_inst(seed=seed, rings=1 if seed % 2 else 0)
    budget = float(inst.cost.sum()) * 0.45
    bf, bf_set = pf.brute_force(inst, budget, W, equity)
    sol = pf.solve(inst, budget, W, equity, time_limit=20, rel_gap=0.0)
    assert sol["status"] == "OPTIMAL"
    assert sol["objective"] == bf                                           # exact optimum, not a heuristic
    assert pf.objective_value(inst, sol["chosen"], W, pf.refs(inst)) == bf
    assert pf.feasible(inst, sol["chosen"], budget, equity)


def test_constraints_hold_on_many_random_instances():
    for seed in range(30):
        inst = rand_inst(n=14, seed=100 + seed, rings=seed % 3)
        for frac, eq in ((0.2, 0), (0.5, 50), (0.9, 50)):
            budget = float(inst.cost.sum()) * frac
            sol = pf.solve(inst, budget, W, eq, time_limit=10)
            assert pf.feasible(inst, sol["chosen"], budget, eq), (seed, frac, eq)


def test_more_budget_never_means_less_benefit():
    inst = rand_inst(n=13, seed=5)
    prev = -1
    for frac in (0.1, 0.2, 0.35, 0.5, 0.8, 1.0):
        v = pf.solve(inst, float(inst.cost.sum()) * frac, W, 0, time_limit=10, rel_gap=0.0)["objective"]
        assert v >= prev; prev = v


def test_people_reached_by_two_sites_are_counted_once():
    h1, h2 = sorted(h3.grid_disk(CENTRE, 1))[:2]
    inst = pf.Instance(site_ids=["a", "b"], hexes=[h1, h2], types=["pocket_park"] * 2, cost=np.array([1e6, 1e6]), cooling=np.zeros(2), carbon=np.zeros(2),
                       high_need=np.array([False, False]), pixels=[np.array([0, 1]), np.array([1, 2])], pixel_people={0: 10.0, 1: 100.0, 2: 20.0}, need=np.zeros(2))
    inst.conflicts = pf.conflicts_for(inst.hexes, 0)
    sites = pd.DataFrame()
    assert pf.refs(inst)["people"] == 120.0                                   # best single site reaches 100 + 20
    both = pf.objective_value(inst, [0, 1], {"cooling": 0, "people": 1, "carbon": 0}, pf.refs(inst))
    assert both == sum(round(pf.SCALE * v / 120.0) for v in (10.0, 100.0, 20.0))   # pixel 1 (100 people) counted once, not twice
    ev_people = sum(inst.pixel_people[p] for p in set(inst.pixels[0]) | set(inst.pixels[1]))
    assert ev_people == 130.0


def test_hand_worked_three_site_toy_case():
    # budget fits any two of three. A cools most, B and C reach the SAME 100 people. Best pair is A + one of B/C (130), not B + C (100).
    hs = sorted(h3.grid_disk(CENTRE, 1))[:3]
    inst = pf.Instance(site_ids=["A", "B", "C"], hexes=hs, types=["mini_forest", "pocket_park", "pocket_park"], cost=np.array([2e6, 2e6, 2e6]),
                       cooling=np.array([30.0, 0.0, 0.0]), carbon=np.zeros(3), high_need=np.array([False] * 3),
                       pixels=[np.array([], dtype=int), np.array([0]), np.array([0])], pixel_people={0: 100.0}, need=np.array([1.0, 2.0, 3.0]))
    inst.conflicts = pf.conflicts_for(inst.hexes, 0)
    w = {"cooling": 0.5, "people": 0.5, "carbon": 0.0}
    sol = pf.solve(inst, 4e6, w, 0, time_limit=5, rel_gap=0.0)
    assert sorted(sol["chosen"])[0] == 0 and len(sol["chosen"]) == 2          # A plus exactly one of B, C
    assert sol["objective"] == pf.brute_force(inst, 4e6, w)[0] == round(pf.SCALE * (0.5 * 1.0 + 0.5 * 1.0))
    greedy = pf.greedy_by_need(inst, 4e6)                                     # "top need first" picks C then B: wastes money on duplicate reach
    assert pf.objective_value(inst, greedy, w, pf.refs(inst)) < sol["objective"]


def test_same_seed_same_answer():
    inst = rand_inst(n=12, seed=9)
    a = pf.solve(inst, float(inst.cost.sum()) * 0.4, W, 50, time_limit=10, rel_gap=0.0)
    b = pf.solve(inst, float(inst.cost.sum()) * 0.4, W, 50, time_limit=10, rel_gap=0.0)
    assert a["chosen"] == b["chosen"] and a["objective"] == b["objective"]


def test_conflict_rings():
    hs = sorted(h3.grid_disk(CENTRE, 2))
    assert pf.conflicts_for([CENTRE, CENTRE], 0) == [(0, 1)]
    nb = [h for h in h3.grid_disk(CENTRE, 1) if h != CENTRE][0]
    assert pf.conflicts_for([CENTRE, nb], 0) == [] and pf.conflicts_for([CENTRE, nb], 1) == [(0, 1)]
    far = [h for h in hs if h3.grid_distance(CENTRE, h) == 2][0]
    assert pf.conflicts_for([CENTRE, far], 1) == []


def _sites_df(n=14, seed=2):
    rng = np.random.default_rng(seed)
    cells = sorted(h3.grid_disk(CENTRE, 3))[:n]
    rows = []
    for i, h in enumerate(cells):
        for t in ("pocket_park", "mini_forest"):
            rows.append({"site_id": f"{h}:{t}", "h3": h, "type": t, "lat": 18.5, "lng": 73.8, "area_ha": float(rng.uniform(0.5, 1.0)), "pop": 400.0,
                         "pop_unserved_300m": 200.0, "dlst_p10": -0.8, "dlst_p50": -0.5, "dlst_p90": -0.2, "need_balanced": float(rng.uniform(0, 100))})
    return pd.DataFrame(rows)


def test_instance_costs_come_from_the_same_engine_as_the_scenario_runner():
    A = P.load(); sites = _sites_df()
    pix = pd.DataFrame({"h3": sites["h3"].iloc[0], "pixel": [1, 2, 3], "people": [10.0, 20.0, 30.0]})
    inst = pf.build_instance(sites, pix, A)
    for i in (0, 1, 5):
        r = S.run(sites.iloc[i].to_dict(), A, mode="base")
        assert inst.cost[i] == pytest.approx(r["cost"]["present_value_inr"]["p50"])
    assert inst.pixels[0].size == 3 and inst.pixels[1].size == 0              # mini-forest does not count toward access
    assert inst.carbon[0] == 0 and inst.carbon[1] > 0                         # pocket park: no carbon estimate


def test_portfolio_totals_add_up_in_base_mode_and_have_ordered_ranges_in_mc():
    A = P.load(); sites = _sites_df()
    pix = pd.concat([pd.DataFrame({"h3": h, "pixel": range(k, k + 3), "people": [10.0, 20.0, 30.0]}) for k, h in zip((0, 2), sites["h3"].unique()[:2])])
    inst = pf.build_instance(sites, pix, A)
    chosen = [0, 1, 4]
    ev = pf.evaluate(inst, chosen, sites, A, budget=1e12, w=W, mode="base")
    assert ev["cost_pv_inr"]["p50"] == pytest.approx(sum(inst.cost[i] for i in chosen))
    assert ev["cooling_person_degrees"]["p50"] == pytest.approx(sum(inst.cooling[i] for i in chosen))
    mc = pf.evaluate(inst, chosen, sites, A, budget=1e12, w=W, draws=600)
    assert mc["cost_pv_inr"]["p10"] < mc["cost_pv_inr"]["p50"] < mc["cost_pv_inr"]["p90"] and mc["prob_within_budget"] == 1.0


def test_run_grid_is_labelled_and_never_loses_to_the_simple_baseline_on_its_own_objective():
    A = P.load(); sites = _sites_df(n=16)
    rng = np.random.default_rng(1)
    pix = pd.concat([pd.DataFrame({"h3": h, "pixel": rng.choice(60, 8, replace=False), "people": rng.integers(5, 50, 8).astype(float)}) for h in sites["h3"].unique()])
    pix = pix.groupby(["h3", "pixel"], as_index=False).first()
    pixmap = pix.drop_duplicates("pixel").set_index("pixel")["people"]
    pix["people"] = pix["pixel"].map(pixmap)
    inst = pf.build_instance(sites, pix, A)
    cfg = {"portfolio": {"presets": {"balanced": W, "heat_first": {"cooling": .6, "people": .2, "carbon": .2}},
                         "budget_multiples_of_median_site_cost": [3, 6, 12], "equity_shares_pct": [0, 50], "no_regret_min_share": 0.75}}
    g = pf.run_grid(inst, sites, A, cfg, time_limit=10, draws=200)
    assert g["status"] == "ok" and len(g["results"]) == 2 * 3 * 2
    for r in g["results"]:
        assert r["solver"]["status"] in ("OPTIMAL", "FEASIBLE")
        if r["equity_pct"] == 0 and r["gain_vs_top_need_pct"] is not None:
            assert r["gain_vs_top_need_pct"] >= -1e-6                       # exact optimum can never be worse than the simple list
        assert r["cost_pv_inr"]["p50"] > 0 or r["n_sites"] == 0
    by = {(r["preset"], r["equity_pct"]): [] for r in g["results"]}
    for r in g["results"]:
        by[(r["preset"], r["equity_pct"])].append(r["objective_norm"])
    for v in by.values():
        assert all(b >= a - 1e-9 for a, b in zip(v, v[1:]))                  # the frontier never falls as the budget grows
