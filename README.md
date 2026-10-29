# EcoMetrix: Green Investment Planner (Pune pilot)

Evidence base for deciding where a city's next rupee of greening should go. **This release covers roadmap milestones M0 to M5 (weeks 1 to 6):** pilot-city audit, baseline layers and dashboard, heat–greenery model, cost and impact engine, demand forecast, need score, candidate sites, and a single-site scenario runner. The budget-constrained portfolio optimiser, scenario comparison and report export are milestones M6 to M9 and are **not built yet**.

Everything on screen comes from open data or from a sourced assumption. There is no demo data, no placeholder numbers and no sign-in. If a source cannot be reached, that layer is marked *failed* with the reason; if a number has no defensible source (for example carbon for pocket parks), the app says "not estimated" rather than inventing one.

```
ecometrix/
├── frontend/      React 19 + Vite 8 + MapLibre 6 + deck.gl 9 (deploy to Vercel)
├── backend/       FastAPI + the cost and impact engine (deploy to Render, native Python, no Docker)
├── pipelines/     data pipeline: tree census, OSM, Landsat, Sentinel-2, WorldCover, WorldPop → H3 grid
├── model/         heat model, demand forecast, need score, candidate sites (+ the M3 baseline)
├── config/        pilot_pune.yaml (the only city-specific file) and assumptions.yaml (every assumed number, with its source)
├── data/outputs/  built data served by the API (committed; empty until you run "Build data")
├── docs/          roadmap (.docx), model cards, data inventory, assumptions register
├── .github/       CI and the "Build data" workflow
└── render.yaml    Render Blueprint
```

## What the app does

| Screen | Milestone | What it shows |
|---|---|---|
| **Atlas** | M3 | Scroll-driven 3D story of Pune's trees, heat and park access with live numbers |
| **Forecast** | M5 · Screen 2 | City population to 2035 with a backtest-error envelope; the backtest table; where growth lands |
| **Priority** | M5 · Screen 3 | Need score map with four visible components and weight presets; ranked candidate sites; **scenario runner** for one site: cost, cooling, people reached, carbon, each as a range with an evidence label, against a fixed budget |
| **Explore** | M3 | Every layer (including need and forecast layers), click a hexagon, exploratory filter |
| **Data audit** | M0 to M5 | Pilot-city checks, per-layer status, model cross-validation (including when the simple model wins) |
| **Method** | all | Evidence labels, layer definitions, limits, and the full **assumptions register** with sources |

## What is real, and what I could not verify

Verified while building (documentation, package registries, tests):

* Current stable package versions; the new majors needed code changes and the project builds and type-checks on them.
* Render free tier (512 MB, sleeps after 15 min idle), Blueprint format, Python version setting.
* OpenFreeMap basemap (no key), Planetary Computer (free anonymous STAC), WorldPop yearly rasters 2000 to 2020 exist (listing seen for 2019 and 2020).
* Tree census: 17 CSV parts on OpenCity. The explainer says 4.09 million trees but the parts add up to about 4.009 million; the audit shows the count actually loaded.
* WHO access rule: at least 0.5 ha within 300 m.
* **Cost and carbon sources** (see `config/assumptions.yaml`): mini-forest cost and density from Afforestt quotes and Mongabay-India (via press), carbon from a 2025 study of three South Indian Miyawaki forests, PMC garden spending from a news report of PMC's own figures, discount rate from NABARD and Institute of Economic Growth. **No Pune rate schedule was found**, so costs are ranges, several of them with a stated "judgement" bound. **No Indian measurement of park carbon was found**, so it is not estimated.

Tested: 17 pipeline, 21 model, 26 backend (API and engine) and 21 UI tests, plus the type-check and production build, all pass. The engine's arithmetic is checked against hand-worked examples (cost present value, carbon curve, budget logic). A whole-chain test runs pipeline-shaped data through the model step, the API and a scenario for each intervention type.

**Not verified: the pipeline and model steps have never run on the live sources.** The build environment could not reach the data servers, so all tests use small stand-in data created inside the tests. The first real run is where surprises will appear, most likely: tree-census CSV column names (auto-detected and reported), Overpass timeouts, Planetary Computer scene counts, the 21 yearly WorldPop reads (a year that cannot be read is skipped and reported; fewer than 5 readable years fails the forecast layer), and whether enough hexagons are mostly park or mostly forest to derive the greenness targets (otherwise cooling shows "not available", never a guess). Layers are independent, so one failure does not stop the others.

## Run it

Requires Python 3.12+ and Node 22.12+.

### 1. Build the data (once, then monthly)

Push the repo to GitHub, then **Actions → Build data → Run workflow**. It runs the pipeline, `baseline_relationship.py` and `run_models.py`, writes a per-layer and per-model status table to the job summary, and commits `data/outputs/`. Read that table first.

Or locally:

```bash
python -m pip install -r pipelines/requirements.txt -r model/requirements.txt
python scripts/build_data.py  # pipeline, then baseline_relationship.py and run_models.py
```

On Windows, use the Python 3.12 launcher explicitly (the project requires Python 3.12 or newer):

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r pipelines/requirements.txt -r model/requirements.txt
.\.venv\Scripts\python.exe scripts/build_data.py
```

Use the virtual-environment Python for each command; plain `pip` can target a different Python installation and mix these packages with unrelated global packages.
If the WorldPop server does not allow windowed reads, the first build downloads its 506 MB baseline raster to `data/raw/` and reuses it on later runs. Keep the build running until that download completes. The equivalent `make data` target is available on systems with GNU Make installed.
Layers can be run separately: `PYTHONPATH=pipelines python -m ecometrix_pipeline.run --only osm,trees`. Set `ECOMETRIX_CONTACT` to your repo URL or email (Nominatim and Overpass expect an identifying User-Agent).

### 2. Run locally

The following commands are for Bash systems with GNU Make. On Windows PowerShell, skip this block and use the Windows commands below.

```bash
pip install -r backend/requirements-dev.txt
make api                                   # http://localhost:8000/docs
cd frontend && npm ci && npm run dev       # http://localhost:5173 (proxies /api to port 8000)
```

On Windows PowerShell, first create the virtual environment if you skipped step 1, then install and run the backend without GNU Make:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r backend/requirements-dev.txt
.\.venv\Scripts\python.exe -m uvicorn app.main:app --app-dir backend --reload --port 8000
```

If step 1 already created `.venv`, skip the `venv` command. Run the install command only if the backend requirements have not yet been installed in that environment.
In a second PowerShell window, run the frontend with `Set-Location frontend; npm ci; npm run dev`.

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
* Cost: present value of capital and upkeep in rupees with Monte Carlo ranges (2,000 draws, fixed seed). Costs are compared with doing nothing. There is no ROI or payback figure: green space earns no revenue in this model.
* Differences from the roadmap, on purpose: straight-line access distance (walking network later); hexagon grid instead of wards (the census uses pre-2017 ward numbers); two intervention types instead of four.

See `docs/` for the roadmap, model cards, data inventory and assumptions register.
