# Model card: portfolio optimiser (M6)

**Code:** `model/portfolio.py` · **Output:** `data/outputs/portfolios.json`

| | |
|---|---|
| Question | Which set of candidate sites does the most good within a budget? |
| Method | Exact integer programming (Google OR-Tools CP-SAT, Apache-2.0), not a heuristic. On small cases the answer is **proven equal to brute force** in `model/tests/test_portfolio.py` (16 random instances, with and without the equity rule and neighbour-separation rules). |
| Decision | Fund or not each candidate site (at its default area); at most one per hexagon; optional gap of hexagon rings between chosen sites |
| Benefits | **Cooling** (person-degrees, adds up across sites; no spill-over credited) · **People newly within 300 m of a park**, counted **once** however many chosen sites reach them (pixel-exact catchments from `site_pixels.parquet`) · **Carbon** (mini-forests only) |
| Objective | Weighted sum of the three benefits, each divided by the best any single site achieves. Weights are policy presets in `config/pilot_pune.yaml` (balanced, heat first, access first, carbon first). |
| Constraints | Budget on the **median present-value cost**; optional **equity rule**: at least half of spend in the top third of sites by need; one site per hexagon |
| Uncertainty | After choosing, each site's cost and benefits are re-drawn (2,000 Monte Carlo draws, fixed seed) and added up; the chance of fitting the budget is reported. Sites are assumed independent. |
| Grid | Budgets are multiples of the median site cost; every preset × budget × equity setting is pre-solved in the model step, so the app only serves proven results and the free web server does no heavy computation |
| Baseline | "Fund the highest-need sites first while the budget lasts." The optimiser is reported against it for every solution; with no equity rule it cannot be worse on the objective (tested) |
| No-regret sites | Chosen in at least 75% of the solutions with no equity rule and a budget at or above the middle of the grid |
| Known limits | Benefits use median values; the result is only as good as the cost, carbon and cooling estimates. If there are more than 3,000 candidates the 3,000 best by benefit per rupee are searched and this is stated in the result. Land acquisition time, politics and construction capacity are not modelled. Sites are estimates of open land, not parcels. |
