# Model card: demand forecast (M5)

**Code:** `model/forecast.py` · **Output:** `forecast.json`, `pop_2025/2030/2035` in `analysis.parquet`

| | |
|---|---|
| Question | How many residents will each hexagon (and the city) have in 2025, 2030 and 2035 if the 2000 to 2020 trend continues? |
| Inputs | WorldPop **unconstrained** yearly population 2000 to 2020 (100 m), summed per hexagon. This is a modelled series, not census counts, and a different product from the 2020 constrained raster used for the baseline. |
| Methods | no change (last value) · straight line, all years · straight line, last 10 years · exponential, all years |
| Selection | **Backtest**: fit on 2000 to 2014, predict 2015 to 2020; lowest weighted absolute percentage error (WAPE) across hexagons wins; a method must beat simpler ones by at least 1%. "No change" is the bar. |
| Uncertainty | Backtest error envelope: smallest and largest relative error of the city total at each horizon across several forecast origins. Beyond the tested horizon the worst case is extended linearly. **Not a statistical interval.** |
| Output | Per-hexagon projections (median only); city series with the envelope |
| Known limits | Policy shocks (new transit, master-plan changes) are not modelled. Projecting a modelled series 15 years ahead is a scenario, not a prediction. An official census anchor is still to be added. |
