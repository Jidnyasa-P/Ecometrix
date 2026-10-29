import sys
from pathlib import Path
import numpy as np
import pandas as pd
import pytest
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import forecast as fc

YEARS = list(range(2000, 2021))


def series(kind, n=300, seed=0, noise=0.02):
    rng = np.random.default_rng(seed)
    base = rng.uniform(50, 500, n)[:, None]
    t = np.array(YEARS)[None, :] - 2000
    if kind == "linear":
        Y = base * (1 + 0.03 * t)
    elif kind == "flat":
        Y = base * np.ones_like(t, dtype=float)
    else:
        Y = base * np.exp(0.03 * t)
    Y = Y * (1 + rng.normal(0, noise, Y.shape))
    df = pd.DataFrame(Y, columns=[f"y{y}" for y in YEARS]); df.insert(0, "h3", [f"c{i}" for i in range(n)])
    return df


def test_straight_line_exact_and_never_negative():
    Y = np.array([[10.0, 12.0, 14.0, 16.0, 18.0, 20.0, 22.0, 24.0]])
    yrs = np.arange(2013, 2021)
    p = fc.predict("linear_all", Y, yrs, np.array([2021, 2025]))
    assert p == pytest.approx(np.array([[26.0, 34.0]]))
    assert fc.predict("naive", Y, yrs, np.array([2030]))[0, 0] == 24.0
    down = np.array([[8.0, 6.0, 4.0, 2.0, 1.0, 0.5, 0.2, 0.1]])
    assert (fc.predict("linear_all", down, yrs, np.array([2040])) >= 0).all()


def test_exponential_matches_exponential_data():
    Y = 100 * np.exp(0.05 * np.arange(10))[None, :]
    p = fc.predict("exponential_all", Y, np.arange(2000, 2010), np.array([2012]))
    assert p[0, 0] == pytest.approx(100 * np.exp(0.05 * 12), rel=1e-6)


def test_growing_city_picks_a_trend_method_and_flat_city_picks_naive():
    g = fc.run(series("linear"), 2014, [2025, 2030, 2035])
    assert g["status"] == "ok" and g["method"] != "naive"
    assert g["backtest"]["methods"][g["method"]]["wape_pct"] < g["backtest"]["methods"]["naive"]["wape_pct"]
    f = fc.run(series("flat", noise=0.0), 2014, [2025, 2030, 2035])
    assert f["method"] == "naive"                                   # a fancier method must beat "no change" to be used


def test_output_shapes_and_growth_column():
    r = fc.run(series("linear"), 2014, [2025, 2030, 2035])
    c = r["_cells"]
    assert {"pop_2020_series", "pop_2025", "pop_2030", "pop_2035", "pop_growth_2035"} <= set(c.columns)
    assert np.allclose(c["pop_growth_2035"], c["pop_2035"] - c["pop_2020_series"])
    s = pd.DataFrame(r["city_series"])
    assert s[s.kind == "history"].year.tolist() == YEARS and s[s.kind == "forecast"].year.min() == 2021 and s.year.max() == 2035
    f = s[s.kind == "forecast"]
    assert (f.low <= f.total).all() and (f.total <= f.high).all()
    spread = (f.high - f.low) / f.total
    assert spread.iloc[-1] > spread.iloc[0]                         # the band widens with the horizon


def test_envelope_contains_realised_errors_it_was_built_from():
    df = series("linear", noise=0.05)
    Y = df[[f"y{y}" for y in YEARS]].to_numpy(); yrs = np.array(YEARS)
    env = fc.envelope(Y, yrs, "linear_all", list(range(2009, 2019)), 15)
    lo, hi = fc.band(env, 3)
    assert lo <= 0 <= hi and hi - lo >= 0


def test_refuses_short_history():
    df = series("linear").iloc[:, :8]
    assert fc.run(df, 2014, [2030])["status"] == "unavailable"
