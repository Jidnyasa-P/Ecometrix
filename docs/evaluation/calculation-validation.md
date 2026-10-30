# Independent recomputation of one site

The person who did **not** write `backend/app/engine/scenario.py` recomputes one mini-forest site and one pocket-park site in a spreadsheet, using only `config/assumptions.yaml` and the site's row in `sites.parquet`, without reading the code.

Steps: set the site's area, horizon and base values (use `mode="base"` numbers: every parameter at its base). Compute: capital cost = m² × Rs/m²; sapling replacement = m² × saplings/m² × (1 − survival) × sapling price ÷ (1 + r); establishment maintenance = m² × Rs/m²/yr × Σ 1/(1+r)^t for t = 1..3; carbon = Σ(yearly rate by age) × scale × area × 44/12; park cost = m² × Rs/m²/yr × Σ 1/(1+r)^t for t = 1..horizon.
Compare with `scenario.run(site, assumptions, mode="base")`. Tolerance: 0.1%. Record both and the difference here. Also confirm units (m², ha, ₹, °C). **Result: not yet done.**
