# EcoMetrix — multi-city urban greening evidence platform

EcoMetrix is a decision-support prototype for understanding urban heat, mapped green space, population exposure and park-access gaps. It currently contains four city profiles:

| City | Country | Currency | State in this archive | Tree inventory | Local finance / carbon model |
|---|---|---:|---|---|---|
| Pune | India | INR | Original pilot configuration; data must pass the release gate | Pune open tree census configured | Enabled using the Pune assumptions pack |
| London | United Kingdom | GBP | Configuration only — not built or validated | Optional; canopy proxy only | Disabled pending local cost and carbon evidence |
| New York City | United States | USD | Configuration only — not built or validated | Optional; canopy proxy only | Disabled pending local cost and carbon evidence |
| Athens | Greece | EUR | Configuration only — not built or validated | Optional; canopy proxy only | Disabled pending local cost and carbon evidence |

**Important:** the presence of a city in the selector does not mean its data has been built. A city is marked *built* only after its own data pipeline, models and release quality gate complete successfully. In this source archive, no fresh live data build for London, New York or Athens has been completed. Do not present those cities' outputs as validated results until their workflows pass.

The global foundation uses open data sources with international coverage where available: OpenStreetMap, ESA WorldCover, Landsat, Sentinel-2 and WorldPop. Tree inventories remain city-specific. When a city has no configured open tree inventory, EcoMetrix does not invent tree counts; it uses land-cover canopy proxies and reports the missing inventory. City outputs and raw downloads are stored separately under `data/cities/<slug>/`.

## What the application contains

- **Atlas:** city overview and story map.
- **Forecast:** population trend and backtest-based projections.
- **Priority:** heat, population, access and growth need score.
- **Plan / Compare:** Pune's cost-aware scenario and portfolio tools. These are disabled outside Pune until a locally sourced and validated finance pack exists.
- **Language:** English, Marathi and Greek can be selected throughout the app. Navigation, footer, key story and page headings, and the Citizen view are localized. Some analytical explanations, chart labels and source text remain English. Marathi and Greek are draft translations and need fluent-speaker review before public use.
- **Explore:** data layers and optional 3D hexagon rendering.
- **Data audit / Evaluation / Method:** layer status, model checks, evidence labels, assumptions and limitations.

All plans are simulations, not built interventions. Candidate sites are analytical areas, not verified parcels. Heat outputs use satellite land-surface temperature, not human-experienced air temperature.

## City-specific design decisions and limitations

- **Projection:** the local UTM EPSG code is calculated from each city's configured centre. The code no longer assumes UTM zone 43N for every place.
- **Boundary:** each city uses Nominatim place queries first, with area sanity checks. A configured bounding-box fallback is explicitly marked and fails the release gate; it is never accepted as a validated city boundary.
- **Population:** WorldPop country codes and per-city URLs are selected from the city profile. Historical population layers remain limited to the available 2000–2020 series.
- **Park access:** London uses the Natural England 2 ha / 300 m local benchmark, but this implementation currently measures straight-line distance, not the separate network-based 15-minute standard. New York uses a 0.5-mile radius as a transparent straight-line proxy only; it is **not** the Trust for Public Land walk-network service-area method. Athens uses a WHO Europe 0.5 ha / 300 m evidence benchmark, not a verified municipal legal standard. Pune's configured threshold is 0.5 ha / 300 m. Every result must display its method and caveat.
- **Costs and carbon:** foreign city packs disable financial optimisation and carbon estimation until comparable local capital, maintenance, planting survival and sequestration sources have been validated. Currency symbols and locale metadata are configured, but that is not a substitute for a local economic model. Pune's assumptions remain INR-specific.
- **Language:** the language selector is global and persists across routes. A persistent notice explains that Marathi and Greek are unreviewed drafts and that some technical/analytical text remains English. Do not publish translated content without fluent-speaker review.
- **Model transfer:** heat/need models must be built and evaluated for each city. Pune model weights or metrics must not be represented as transferable to another city.

## Repository layout

```text
ecometrix/
├── frontend/                  React + TypeScript + Vite + MapLibre + deck.gl
├── backend/                   FastAPI API and Pune-only finance/scenario engine
├── pipelines/                 city-aware boundary, OSM, satellite and population pipeline
├── model/                     heat, forecast, need score, candidate sites and optimiser
├── config/
│   ├── registry.yaml           city selector and default city
│   ├── cities/                 one city configuration per profile
│   └── assumptions/            one sourced assumptions pack per city
├── data/cities/<slug>/         isolated raw downloads and outputs per city
├── docs/                       model cards, decision log and evaluation protocols
├── .github/workflows/          CI, single-city and opt-in four-city build workflows
└── render.yaml                 Render backend blueprint
```

## Requirements

- **Python:** use Python **3.13.17** for this Windows setup. Python 3.13.18 (released October 25, 2026) is a source-only security release; 3.13.17 is the final 3.13 release with a standard Windows installer. The project stays on 3.13.17 because its pinned geospatial/scientific stack is configured for this installable runtime, rather than assuming every wheel is ready on a newer feature branch. Render and CI use the same version. Update pip inside the virtual environment after installation.
- **Node.js:** use Node **22.23.4** or later in the Node 22 line. `.node-version` contains the tested target. This is important: newer transitive frontend packages reject older Node 22 maintenance releases.
- Git and a network connection are required to install packages and retrieve open geospatial data.

The package files are pinned. Use the root `requirements.txt` as the single install entry point; it includes the backend, model, pipeline and test dependencies. CI runs `pip check`, Python tests, TypeScript checks, frontend tests and the production build on the pinned runtimes. This editing environment could not reach package indexes, so a clean install could not be independently completed here; the CI workflow is the first networked clean-install verification.

## Run on Windows 11 (PowerShell)

From the repository root:

```powershell
# Python environment
py -3.13 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m pip check

# Frontend dependencies
cd frontend
npm ci
cd ..
```

If PowerShell blocks environment activation, run `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass` in that terminal and activate again.

### Build all four city pilots on GitHub Actions

The repository includes an opt-in matrix workflow at **Actions → Build all configured city pilots**. Check the confirmation box to run Pune, London, New York and Athens in parallel. Each city is built in its own job; only cities whose data, model and audit quality gate passes are uploaded and committed. Failed cities are not marked as built. This requires the project to be pushed to GitHub with Actions write permission enabled. The four-city run downloads global datasets and can use substantial runner time and artifact storage.

A successful workflow run is the required evidence that a city build passed. A city profile alone is not evidence of a build. Review the workflow summary and each city's `release_check.json` before claiming that city is validated.

### Build one city

The build requires internet access to Nominatim, Overpass, WorldPop and Microsoft Planetary Computer. Run the stages in order. The output and raw downloads are isolated by city.

```powershell
# Pune (default pilot)
$env:PYTHONPATH = "pipelines"
python -m ecometrix_pipeline.run --city pune
python model/baseline_relationship.py --city pune
python model/run_models.py --city pune
python -m ecometrix_pipeline.quality_gate --city pune

# To build a different configured city, replace 'pune' consistently:
# london | new-york | athens
```

Equivalent Make target: `make data CITY=london` (or `CITY=new-york`, `CITY=athens`, `CITY=pune`). The target runs all four stages including the release gate. `release_check.json` is only written after the required data, model and audit checks pass. A failed build removes any older passing marker so stale success cannot be shown.

Read the layer and model manifests, the audit and the `release_check.json` before using a city. The current quality gate rejects a configured bounding-box fallback, missing required satellite/population layers, stale/poorly covered latest imagery, incomplete core models and failed audit checks. First builds can take a long time and may need source-specific troubleshooting.

### Run the API and website locally

Open two terminals from the repository root, with the virtual environment active in each.

Terminal 1 — API:

```powershell
python -m uvicorn app.main:app --app-dir backend --reload --port 8000
```

Terminal 2 — frontend:

```powershell
cd frontend
npm run dev
```

Open `http://localhost:5173`. The city selector changes the `?city=` query parameter and all API requests follow the selected city. A configured but unbuilt city is clearly shown as not built; it is not filled with Pune's data.

### Run checks

```powershell
python -m compileall -q pipelines model backend
$env:PYTHONPATH = "pipelines"
python -m pytest pipelines/tests -q
python -m pytest model/tests -q
python -m pytest backend/tests -q
cd frontend
npm run typecheck
npm test
npm run build
```

A full end-to-end release test must be done after each city has real pipeline outputs. Unit tests and static checks cannot establish that remote city data sources are reachable or that the resulting study boundary is correct.

## Data build automation

Push the repository to GitHub. Choose **Actions → Build data → Run workflow**, then select one city. The scheduled workflow rebuilds Pune by default; other cities are built on demand until their independent pipelines are proven stable. The workflow commits only that city's output directory and stops before committing if the quality gate fails.

## Deploy

- **Backend:** use the Render Blueprint in `render.yaml`. Set `ALLOWED_ORIGINS` to the deployed Vercel URL(s). The backend reads each city's own assumptions pack and output directory.
- **Frontend:** deploy `frontend/` to Vercel, set `VITE_API_URL` to the Render service URL (no trailing slash), and ensure the API has the correct allowed origin.
- Do not deploy a city as a public validated pilot until its own output has `release_check.json` with `status: passed` and a human has checked the boundary, source provenance, maps and representative locations.

## Performance choices

- The site uses **2D maps by default**. Only the Explore page offers optional 3D extrusion.
- MapLibre's worker URL is explicitly registered for Vite builds.
- Initial camera fitting occurs after the map is loaded and resized; requested padding is clamped to canvas size to avoid impossible `fitBounds` geometry.
- Deck.gl layers do not enable picking unless the map is interactive. Extrusion, animation and high-cost visual effects are not enabled on the story pages.

These changes reduce unnecessary GPU work, but performance still depends on browser, integrated graphics, data size and viewport. Validate on a modest Windows laptop as well as a desktop browser.

## Evidence and responsible use

Every city must be checked independently. Global satellite and population products do not guarantee equal quality, temporal coverage, resolution, or local representativeness. OSM coverage varies by place. Population is a gridded estimate. Tree canopy from land cover is not a tree count. Straight-line park distance is not walkability. Candidate land is not a confirmed available parcel. The models are planning aids, not medical, legal or engineering advice, and must not be used as a substitute for field surveys or local stakeholder review.
