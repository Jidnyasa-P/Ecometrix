"""Hand-worked checks. Expected values are computed here with plain Python, in a different shape from the engine."""
import numpy as np
import pytest
from app.engine import params as P, scenario as S

A = P.load()
BASE = dict(mode="base")


def site(t="mini_forest", area=1.0, **kw):
    s = {"site_id": f"x:{t}", "type": t, "area_ha": area, "pop": 500.0, "pop_unserved_300m": 320.0,
         "dlst_p10": -0.9, "dlst_p50": -0.6, "dlst_p90": -0.3}
    s.update(kw)
    return s


def annuity(r, n): return sum(1 / (1 + r) ** k for k in range(1, n + 1))


def test_mini_forest_cost_by_hand():
    r = S.run(site(area=1.0), A, horizon_years=5, **BASE)
    rate = 0.06
    capex = 10_000 * 550
    repl = 10_000 * 3 * (1 - 0.79) * 100 / 1.06
    maint = 10_000 * 88.4 * annuity(rate, 3)
    assert r["cost"]["present_value_inr"]["p50"] == pytest.approx(capex + repl + maint, rel=1e-9)
    assert r["cost"]["breakdown_base_inr"]["capital"] == pytest.approx(capex)


def test_mini_forest_carbon_by_hand():
    r = S.run(site(area=2.0), A, horizon_years=5, **BASE)
    rates = [5.284 / 2, 5.284, (5.284 + 20.042) / 2, 20.042, 33.084]       # linear from zero at age 0; measured at 2, 4, 5
    expected = sum(rates) * 0.8 * 2.0 * (44 / 12)
    assert r["benefits"]["carbon"]["t_co2e"]["p50"] == pytest.approx(expected, rel=1e-3)
    # beyond year 5 the year-5 rate is held and multiplied by the post-5 factor
    r8 = S.run(site(area=1.0), A, horizon_years=8, **BASE)
    exp8 = (sum(rates) + 3 * 33.084 * 0.75) * 0.8 * (44 / 12)
    assert r8["benefits"]["carbon"]["t_co2e"]["p50"] == pytest.approx(exp8, rel=1e-3)


def test_pocket_park_cost_access_and_no_carbon():
    r = S.run(site("pocket_park", area=0.8), A, horizon_years=10, **BASE)
    assert r["cost"]["present_value_inr"]["p50"] == pytest.approx(8_000 * 88.4 * annuity(0.06, 10), rel=1e-9)
    assert r["benefits"]["people_newly_served"]["value"] == 320.0
    assert r["benefits"]["carbon"]["available"] is False and "United States" in r["benefits"]["carbon"]["note"]
    assert "inr_per_t_co2e" not in r["cost_effectiveness"]
    assert r["cost_effectiveness"]["inr_per_person_newly_served"]["p50"] == pytest.approx(r["cost"]["present_value_inr"]["p50"] / 320.0)


def test_small_park_and_forest_serve_nobody():
    small = S.run(site("pocket_park", area=1.0), A, area_ha=0.3, **BASE)
    assert small["benefits"]["people_newly_served"]["value"] == 0.0 and "smaller than" in small["benefits"]["people_newly_served"]["note"]
    forest = S.run(site("mini_forest"), A, **BASE)
    assert forest["benefits"]["people_newly_served"]["value"] == 0.0


def test_cooling_person_degrees_and_area_scaling():
    full = S.run(site(area=1.0), A, **BASE)
    half = S.run(site(area=1.0), A, area_ha=0.5, **BASE)
    assert full["benefits"]["cooling"]["delta_lst_c"]["p50"] == pytest.approx(-0.6)
    assert full["benefits"]["cooling"]["person_degrees"]["p50"] == pytest.approx(0.6 * 500)
    assert half["benefits"]["cooling"]["delta_lst_c"]["p50"] == pytest.approx(-0.3)
    assert half["cost"]["present_value_inr"]["p50"] < full["cost"]["present_value_inr"]["p50"]


def test_missing_cooling_is_reported_not_invented():
    r = S.run(site(dlst_p10=np.nan, dlst_p50=np.nan, dlst_p90=np.nan), A, **BASE)
    assert r["benefits"]["cooling"]["available"] is False and "No cooling estimate" in r["benefits"]["cooling"]["note"]
    assert "inr_per_person_degree_c" not in r["cost_effectiveness"]


def test_monte_carlo_range_is_ordered_reproducible_and_brackets_base():
    a = S.run(site(), A, draws=3000, seed=7)
    b = S.run(site(), A, draws=3000, seed=7)
    assert a == b                                                        # same seed, same answer
    c = a["cost"]["present_value_inr"]
    assert c["p10"] < c["p50"] < c["p90"]
    base = S.run(site(), A, **BASE)["cost"]["present_value_inr"]["p50"]
    assert c["p10"] < base < c["p90"]
    k = a["benefits"]["carbon"]["t_co2e"]
    assert k["p10"] < k["p50"] < k["p90"]


def test_budget_logic():
    s = site(area=1.0)
    cost = S.run(s, A, **BASE)["cost"]["present_value_inr"]["p50"]
    ok = S.run(s, A, budget_inr=cost * 2, draws=2000)["budget"]
    assert ok["p50_within_budget"] and ok["probability_within_budget"] > 0.95 and ok["max_area_ha_at_p50_cost"] == pytest.approx(1.0)
    tight = S.run(s, A, budget_inr=cost / 4, draws=2000)["budget"]
    assert not tight["p50_within_budget"] and tight["probability_within_budget"] < 0.05
    assert tight["max_area_ha_at_p50_cost"] == pytest.approx(0.25, rel=0.15)


def test_input_validation():
    with pytest.raises(ValueError): S.run(site(area=1.0), A, area_ha=1.5)
    with pytest.raises(ValueError): S.run(site(area=1.0), A, area_ha=0)
    with pytest.raises(ValueError): S.run(site("street_tree"), A)


def test_every_assumption_has_a_source_label_and_ordered_range():
    def walk(d, path=""):
        for k, v in d.items():
            if isinstance(v, dict):
                if {"low", "base", "high"} <= set(v):
                    assert v["low"] <= v["base"] <= v["high"], path + k
                if "label" in v or "source" in v:
                    assert v.get("source"), f"{path}{k} has no source"
                    assert v.get("label") in ("ASSUMED", "CONSTANT", None), path + k
                walk(v, path + k + ".")
    walk(A)
