# Data inventory (Milestone M0)

| Dataset | Used for | Access | Licence | Verified by |
|---|---|---|---|---|
| Pune Tree Census 2019 (17 CSV parts) | tree density | CKAN API at newdata.opencity.in, package `f00d83b8-c70f-4fff-9ac7-9a6ab4255edf` | Public domain | Dataset page and current resource metadata checked. CSV column names are NOT known in advance: the pipeline detects them and records what it found |
| OpenStreetMap parks, forests | park access, mapped green | Overpass API | ODbL | Standard API; completeness for Pune unknown, reported in the audit |
| Landsat 8/9 Collection 2 Level-2 | surface temperature | Microsoft Planetary Computer STAC (`landsat-c2-l2`), free anonymous access | Public domain | Catalog documented; scenes counted by the audit at build time |
| Sentinel-2 L2A | NDVI | Planetary Computer (`sentinel-2-l2a`) | Copernicus, free and open | As above |
| ESA WorldCover | built-up and tree-cover share | Planetary Computer (`esa-worldcover`) | CC BY 4.0 | Latest version found at build time |
| WorldPop constrained 2020, 100 m, India | population | data.worldpop.org (506 MB GeoTIFF, read by window) | CC BY 4.0 | File listing seen |
| Pune boundary | study area | Nominatim lookup, validated; bounding-box fallback is flagged | ODbL | Validated at build time |
| Basemap | map background | OpenFreeMap (positron, dark styles), no key | OSM-based, free | Documentation checked |
| Cost benchmarks | later milestones | manual | n/a | **Not collected yet** (Person B) |

Known data-quality note: the OpenCity explainer quotes 4.09 million trees, but the 17 parts are listed as 16 x 250,000 + 9,000 = about 4.009 million. The audit shows the number actually loaded.

## Added in milestones M4 and M5

| Dataset | Used for | Access | Licence | Verified by |
|---|---|---|---|---|
| WorldPop unconstrained yearly 2000 to 2020, 100 m | demand forecast history | data.worldpop.org windowed GeoTIFF read; falls back to a study-area TIFF export from WorldPop's time-aware ArcGIS ImageServer if byte-range reads are unavailable | CC BY 4.0 | ImageServer exposes annual 2000–2020 slices; years that fail on both sources are reported, not filled |
| Cost and carbon sources | assumptions register | see `config/assumptions.yaml` | n/a | Searched and recorded with citations; no Pune rate schedule found |

## Added in milestones M6 to M8

| Output | Used for | Produced by |
|---|---|---|
| `site_pixels.parquet` (hexagon, population pixel, unserved people) | exact catchments, so people reached by two sites are counted once | `pipelines` (needs the constrained 2020 population and OSM parks) |
| `portfolios.json`, `sensitivity.json` | pre-solved plans and the tornado analysis | `model/run_models.py` |
