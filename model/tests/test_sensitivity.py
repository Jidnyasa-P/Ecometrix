import sys
from pathlib import Path
import h3
import numpy as np
import pandas as pd
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import sensitivity as sv
from app.engine import params as P

A = P.load()


def sites():
    c = sorted(h3.grid_disk(h3.latlng_to_cell(18.52, 73.85, 9), 3))[:10]
    rows = [{"site_id": f"{h}:{t}", "h3": h, "type": t, "lat": 18.5, "lng": 73.8, "area_ha": 0.5 + 0.1 * i, "pop": 400.0, "pop_unserved_300m": 200.0,
             "dlst_p10": -0.8, "dlst_p50": -0.5, "dlst_p90": -0.2} for i, h in enumerate(c) for t in ("pocket_park", "mini_forest")]
    return pd.DataFrame(rows)


def test_tornado_directions_and_ordering():
    r = sv.run(sites(), A)
    assert r["status"] == "ok" and set(r["types"]) == {"pocket_park", "mini_forest"}
    mf = r["types"]["mini_forest"]
    rows = {x["parameter"]: x for x in mf["rows"]}
    cap = rows["mini_forest.capex_inr_per_m2"]["effects"]["cost_pv_inr"]
    assert cap["at_low"] < mf["base"]["cost_pv_inr"] < cap["at_high"]                 # dearer capital, dearer project
    sc = rows["mini_forest.carbon_scale"]["effects"]["carbon_t_co2e"]
    assert sc["at_low"] < mf["base"]["carbon_t_co2e"] < sc["at_high"]
    sw = [x["max_relative_swing"] for x in mf["rows"]]
    assert sw == sorted(sw, reverse=True)                                             # largest influence first
    pk = {x["parameter"]: x for x in r["types"]["pocket_park"]["rows"]}
    assert "pocket_park.annual_all_in_cost_inr_per_m2" in pk and "mini_forest.capex_inr_per_m2" not in pk
