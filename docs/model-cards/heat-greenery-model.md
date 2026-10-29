# Model card: heat–greenery model (M4)

**Code:** `model/heat_model.py` · **Output:** `data/outputs/heat_model.json`, cooling ranges in `sites.parquet`

| | |
|---|---|
| Question | How does pre-monsoon surface temperature vary with vegetation across Pune's hexagons, holding built-up and water share fixed, and what would it be if a site became greener? |
| Inputs | Per hexagon: Landsat 8/9 surface temperature (target), Sentinel-2 NDVI, ESA WorldCover built-up share, water share |
| Candidates | mean only · straight line on NDVI · straight line on all three · gradient boosting with monotonic constraints (NDVI up means temperature down) |
| Selection | Lowest cross-validated RMSE, but a more complex model must beat the best simpler one by at least 1% |
| Validation | 5-fold **spatial block** cross-validation (H3 resolution-6 blocks held out whole), never random splits; explicit check that a sweep of NDVI never raises predicted temperature; permutation importance on held-out blocks |
| Counterfactual | Raise the hexagon's NDVI toward a **data-derived target** (median NDVI of Pune's own hexagons that are at least 50% mapped park, or forest, in OpenStreetMap), in proportion to the share of the hexagon the site covers. Built-up and water are held fixed. |
| Range | 40 block-bootstrap refits; P10, P50, P90 of the predicted change |
| Output | Change in the hexagon's surface temperature (negative means cooler), at maturity |
| Not claimed | Air-temperature change; proof of causation; cooling in neighbouring hexagons (none is credited); cooling before the planting matures |
| Known limits | Association across space, not an experiment. LST is a mid-morning snapshot. The target NDVI is a dry-season value for mapped parks and forests; mapped parks can be incomplete. Elevation is not a feature (no DEM ingested yet). Response is scaled in proportion to area when a user shrinks a site. |
| Honest comparison | The cross-validation table (all four models) is on the Data audit page after each build, including when the simple model wins. |
