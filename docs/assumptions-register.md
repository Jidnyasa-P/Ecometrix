# Assumptions register

The single source of truth is **`config/assumptions.yaml`**, read by the cost and impact engine and shown on the app's Method page. Every entry has a low / base / high range (or a stated value), a label, and a source. Values with no direct source say "judgement" in their source text.

| Parameter | Base (range) | Where it comes from |
|---|---|---|
| Discount rate | 6% (3.72% to 8%) | NABARD social-discount-rate assessment; Institute of Economic Growth WP 388 |
| Mini-forest capital cost | Rs 550/m² (300 to 800) | Afforestt quote of Rs 50,000 to 60,000 per 100 m² (Citizen Matters); low from sapling price; high is judgement |
| Sapling price | Rs 100 (80 to 140) | Citizen Matters ("over Rs 100") |
| Sapling survival | 79% (50% to 92%) | UK Tree Council Miyawaki trial; Afforestt (self-reported); low is judgement |
| Establishment-care cost | Rs 88.4/m²/yr for 3 years (±50%) | PMC garden spending ÷ area (Bridge Chronicle, Aug 2026): Rs 108.46 crore ÷ 5 years ÷ 24.53 lakh m² |
| Carbon, mini-forest | 5.3, 20.0, 33.1 Mg C/ha/yr at ages 2, 4, 5 (×0.5 to 1.0) | Roy et al. 2025, three Miyawaki forests in Bengaluru and Palakkad |
| Pocket-park cost | Rs 88.4/m²/yr all-in (±50%) | Same PMC figure; a crude proxy until a rate schedule is found |
| Pocket-park carbon | **not estimated** | No Indian measurement found |
| Park access | at least 0.5 ha within 300 m | WHO Regional Office for Europe, 2016 |
| Candidate-site sizes, season, cloud limit | see `config/pilot_pune.yaml` | project choices |

Not yet sourced (and so not used): Pune's own rate schedule for new parks and plantations, road-side tree maintenance costs, green-roof costs.
