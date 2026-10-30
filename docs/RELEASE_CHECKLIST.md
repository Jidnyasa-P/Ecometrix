# Release checklist (week 10)

- [ ] **Build data** workflow run; every layer and model module OK or its failure documented in README
- [ ] Open `audit.json`, `manifest.json`, `models_manifest.json`; check tree count (4,009,000 vs 4,090,000), boundary source, scene counts, yearly WorldPop years read
- [ ] Look at the maps in Explore: temperature, greenness, tree density, population, park access look plausible for Pune
- [ ] Spot-check sites and complete `docs/evaluation/*` templates
- [ ] `make test` passes from a clean checkout; CI green
- [ ] Render service healthy (`/api/health`), `ALLOWED_ORIGINS` set to the Vercel URL; Vercel has `VITE_API_URL`; optional `VITE_FEEDBACK_URL` set for the citizen view
- [ ] Phone check: Atlas, Plan, Citizen view; cold-start message appears and clears
- [ ] Marathi reviewed by a fluent speaker (then delete the notice in `City.tsx`)
- [ ] Usability test done and recorded; top issues fixed
- [ ] Backup video recorded; printable report exported
- [ ] Attributions visible (OSM ODbL, WorldPop and WorldCover CC BY 4.0, Copernicus, USGS, OpenFreeMap, OpenCity)
- [ ] No secrets in the repo; tag the release
