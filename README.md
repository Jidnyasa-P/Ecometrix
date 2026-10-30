# EcoMetrix: Green Investment Planner (Pune pilot)

Evidence base for deciding where a city's next rupee of greening should go. **This release covers all ten weeks of the roadmap (M0 to M9):** pilot-city audit, baseline layers, heat model, cost and impact engine, demand forecast, need score, candidate sites, an **exact portfolio optimiser**, plan comparison, evidence cards, a printable report, an English and Marathi citizen view, and an evaluation page with sensitivity analysis.

Everything on screen comes from open data or from a sourced assumption. There is no demo data, no placeholder numbers and no sign-in. If a source cannot be reached, that layer is marked *failed* with the reason; if a number has no defensible source (for example carbon for pocket parks), the app says "not estimated". All plans are **simulations** compared with doing nothing: nothing has been built.

```
ecometrix/
├── frontend/      React 19 + Vite 8 + MapLibre 6 + deck.gl 9 (deploy to Vercel)
├── backend/       FastAPI + the cost and impact engine (deploy to Render, native Python, no Docker)
├── pipelines/     data pipeline: tree census, OSM, Landsat, Sentinel-2, WorldCover, WorldPop → H3 grid
├── model/         heat model, forecast, need score, candidate sites, portfolio optimiser, sensitivity
├── config/        pilot_pune.yaml (the only city-specific file) and assumptions.yaml (every assumed number, with its source)
├── data/outputs/  built data served by the API (committed; empty until you run "Build data")
├── docs/          roadmap, model cards, evaluation protocols, demo script and Q&A, release checklist, decision log
├── .github/       CI and the "Build data" workflow
└── render.yaml    Render Blueprint
```

## What the app does

| Screen | Milestone | What it shows |
|---|---|---|
| **Atlas** | M3 | Scroll-driven 3D story of Pune's trees, heat and park access with live numbers |
| **Forecast** | M5 | City population to 2035 with a backtest-error envelope; the backtest table; where growth lands |
| **Priority** | M5 | Need score map with four visible components and weight presets; ranked candidate sites; single-site scenario runner |
| **Plan** | M6 | Best portfolio under a budget from an exact optimiser: presets, budget, equity rule; people counted once; cost, cooling and carbon ranges; do-nothing baseline; comparison with "fund highest need first"; evidence card per site |
| **Compare** | M7 | Up to three plans side by side with doing nothing, and what differs |
| **Report** | M7 | Printable plan summary with assumptions, limits and sources (print to PDF) |
| **Citizen view** | M7 | Plain-language "what is planned near me" in English and Marathi (Marathi is flagged as not yet reviewed) |
| **Explore** | M3 | Every layer, click a hexagon, exploratory filter |
| **Data audit** | M0 to M8 | Pilot-city checks, per-layer status, model cross-validation |
| **Evaluation** | M8 | Model results, sensitivity (tornado), what we can and must not claim, human checks still open |
| **Method** | all | Evidence labels, layer definitions, limits, assumptions register with sources |

## What is real, and what I could not verify

Verified while building (documentation, package registries, tests):

* Current stable package versions; the new majors needed code changes and the project builds and type-checks on them.
* Render free tier (512 MB, sleeps after 15 min idle), Blueprint format, Python version setting.
* OpenFreeMap basemap (no key), Planetary Computer (free anonymous STAC), WorldPop yearly rasters 2000 to 2020 exist (listing seen for 2019 and 2020).
* Tree census: 17 CSV parts on OpenCity. The explainer says 4.09 million trees but the parts add up to about 4.009 million; the audit shows the count actually loaded.
* WHO access rule: at least 0.5 ha within 300 m.
* **Cost and carbon sources** (see `config/assumptions.yaml`): mini-forest cost and density from Afforestt quotes and Mongabay-India (via press), carbon from a 2025 study of three South Indian Miyawaki forests, PMC garden spending from a news report of PMC's own figures, discount rate from NABARD and Institute of Economic Growth. **No Pune rate schedule was found**, so costs are ranges, several of them with a stated "judgement" bound. **No Indian measurement of park carbon was found**, so it is not estimated.

Tested at release: **18 pipeline, 47 model (including exact optimiser proofs), 27 backend and 83 frontend tests**, plus type-check, production build and automated accessibility checks (contrast of every text pair in both themes, lightness of map ramps, minimum font size). The optimiser is proven equal to brute force on 16 random instances (with equity and separation rules). The engine's arithmetic is checked against hand-worked examples. A whole-chain test runs pipeline-shaped data through the model step, the API, a scenario and portfolios.

**Not verified: the pipeline and model steps have never run on the live sources, and the interface has never been seen in a browser by the author.** The build environment could not reach the data servers, so all tests use small stand-in data created inside the tests. The first real run is where surprises will appear, most likely: tree-census CSV column names (auto-detected and reported), Overpass timeouts, Planetary Computer scene counts, the 21 yearly WorldPop reads (a year that cannot be read is skipped and reported; fewer than 5 readable years fails the forecast layer), and whether enough hexagons are mostly park or mostly forest to derive the greenness targets (otherwise cooling shows "not available", never a guess). Layers are independent, so one failure does not stop the others. The portfolio step needs `site_pixels.parquet` (the exact catchments); without it the Plan screen says so and shows nothing in its place.

**Human checks not done at release** (protocols in `docs/evaluation/`): five-person usability test, independent spreadsheet recomputation, 30-site satellite spot-check and 20-site expert review, fluent-speaker review of the Marathi text, OSM versus municipal park list, and the labels audit.

## Run it

Requires Python 3.12+ and Node 22.12+.

### 1. Build the data (once, then monthly)

Push the repo to GitHub, then **Actions → Build data → Run workflow**. It runs the pipeline, `baseline_relationship.py` and `run_models.py` (which also solves the portfolio grid; allow up to a few hours), writes a per-layer and per-model status table to the job summary, and commits `data/outputs/`. Read that table first.

Or locally:

```bash
pip install -r pipelines/requirements.txt -r model/requirements.txt
make data         # pipeline, then model/baseline_relationship.py, then model/run_models.py
```

Layers can be run separately: `PYTHONPATH=pipelines python -m ecometrix_pipeline.run --only osm,trees`. Optional `VITE_FEEDBACK_URL` (Vercel) gives the citizen view a feedback button. Set `ECOMETRIX_CONTACT` to your repo URL or email (Nominatim and Overpass expect an identifying User-Agent).

### 2. Run locally

```bash
pip install -r backend/requirements-dev.txt
make api                                   # http://localhost:8000/docs
cd frontend && npm ci && npm run dev       # http://localhost:5173 (proxies /api to port 8000)
```

### 3. Deploy

**Backend on Render (free, no Docker):** commit `data/outputs/` (step 1) → Render dashboard → New → **Blueprint** → select the repo (`render.yaml`). Set `ALLOWED_ORIGINS` to your Vercel URL (comma-separate several; for preview URLs also set `ALLOWED_ORIGIN_REGEX`, e.g. `https://ecometrix-.*\.vercel\.app`). The service reads `config/assumptions.yaml` from the repo, so editing an assumption and pushing changes the scenario results after redeploy.

**Frontend on Vercel (free Hobby plan; check Vercel's terms for your use):** import the repo, **Root Directory** `frontend`, environment variable `VITE_API_URL` = your Render URL (no trailing slash). The first visit after a quiet period shows "Waking the server" for up to about a minute: that is the free Render tier.

### Tests

```bash
make test
```

## Method notes

* Grid: H3 resolution 9 (about 0.1 km² per hexagon) over a 30 m metric pixel grid (UTM 43N).
* Heat: Landsat 8/9 surface temperature, cloud-masked median of March to May 2024 to 2026. Mid-morning **surface** temperature, not air temperature.
* Heat model: compared with simple baselines under spatial block cross-validation; the ML model is used only if it wins by at least 1%; NDVI is constrained so more vegetation never predicts hotter.
* Cooling per site: the model's predicted change when the hexagon's NDVI moves toward the typical NDVI of Pune's own mapped parks or forests, in proportion to the site's share of the hexagon. No spill-over to neighbours is credited.
* Forecast: simple trend methods chosen by a backtest (train 2000 to 2014, test 2015 to 2020); "no change" is the bar. The band is a backtest error envelope, not a statistical interval.
* Need score: weighted percentile ranks of heat, residents, park-access gap and growth. Weights are policy choices, shown as presets. Resident vulnerability is not included (no open data built).
* Candidate sites: estimated open land per hexagon (bare + grass + shrub cover minus mapped parks and forest). **Not parcels; every site needs field verification.** Two types only (pocket park, mini-forest); street trees and green roofs need data that is not built.
* Portfolios: exact integer programming (OR-Tools CP-SAT); benefits are cooling person-degrees, people newly within 300 m of a park (pixel-exact, counted once) and carbon, normalised and weighted by policy presets; budget and an optional equity rule are constraints; solved on a grid of budgets in the model step.
* Cost: present value of capital and upkeep in rupees with Monte Carlo ranges (2,000 draws, fixed seed). Costs are compared with doing nothing. There is no ROI or payback figure: green space earns no revenue in this model.
* Differences from the roadmap, on purpose: straight-line access distance (walking network later); hexagon grid instead of wards (the census uses pre-2017 ward numbers); two intervention types instead of four; the optimiser's results are pre-solved on a grid of budgets rather than solved per request.

See `docs/` for the roadmap, model cards, data inventory and assumptions register.
