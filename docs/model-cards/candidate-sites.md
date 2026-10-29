# Model card: candidate sites (M5)

**Code:** `model/sites.py` · **Output:** `sites.parquet`

A site is a patch of **open land** inside one hexagon, estimated as (bare + grass + shrub cover from ESA WorldCover) minus (hectares OpenStreetMap already maps as park or forest), floored at zero. Two intervention types:

| Type | Minimum / maximum site | Counts toward park access? |
|---|---|---|
| Pocket park | 0.5 ha (WHO minimum) / 2.0 ha | Yes, if at least 0.5 ha |
| Dense mini-forest | 0.1 ha / 1.0 ha | No (assumed fenced); policy choice in `assumptions.yaml` |

Only hexagons with modelled residents become candidates. **A site is not a parcel:** ownership, legality, soil and access are unknown, and every site is flagged *candidate: needs field verification*. Street-tree corridors and green roofs are not included because road-side tree counts and rooftop data are not built.
