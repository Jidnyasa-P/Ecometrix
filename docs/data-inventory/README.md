# Data inventory (Milestone M0)

| Dataset | Used for | Access | Licence | Verified by |
|---|---|---|---|---|
| Pune Tree Census 2019 (17 CSV parts) | tree density | CKAN API at data.opencity.in, package slug `pune-tree-census-2019` | Public domain | Dataset page and current resource metadata checked. CSV column names are NOT known in advance: the pipeline detects them and records what it found |
| OpenStreetMap parks, forests | park access, mapped green | Overpass API | ODbL | Standard API; completeness for Pune unknown, reported in the audit |
| Landsat 8/9 Collection 2 Level-2 (pre-monsoon baseline) | model heat input | Microsoft Planetary Computer STAC (`landsat-c2-l2`), free anonymous access | Public domain | Stable March–May seasonal composites; scenes and acquisition dates counted at build time |
| Landsat 8/9 Collection 2 Level-2 (latest) | judge-facing recent surface-temperature map | Same STAC collection, queried over a rolling 180-day window on each daily build | Public domain | Manifest records newest acquisition, age, scenes, clear days and percentage of cells with valid pixels. Near-real-time, not live sensor data |
| Sentinel-2 L2A (pre-monsoon baseline) | model greenness input | Planetary Computer (`sentinel-2-l2a`) | Copernicus, free and open | Stable March–May seasonal composites; scenes and acquisition dates counted at build time |
| Sentinel-2 L2A (latest) | judge-facing recent greenness map | Same STAC collection, queried over a rolling 180-day window on each daily build | Copernicus, free and open | Manifest records newest acquisition, age, scenes, clear days and percentage of cells with valid pixels. Near-real-time, not live sensor data |
| ESA WorldCover | built-up and tree-cover share | Planetary Computer (`esa-worldcover`) | CC BY 4.0 | Static reference product, only 2020 and 2021 editions; do not describe it as current land cover |
| WorldPop constrained 2020, 100 m, India | population | data.worldpop.org (506 MB GeoTIFF, read by window) | CC BY 4.0 | File listing seen |
| Pune boundary | study area | Preferred: 2025 PMC Electoral Wards KML (41 wards) from the OpenCity `pune-wards-info` catalogue, credited to Parisar; polygons are dissolved and checked against the expanded PMC area (approximately 519 km²). Secondary: validated OSM Nominatim boundary within the same area sanity range. Last resort: configured bounding box, explicitly flagged and blocked from the scheduled publish workflow | Public Domain for the OpenCity resource; OSM fallback ODbL | Resource id, format, credit, resource and package modified dates, area and ward-feature count are recorded in `manifest.json`; fallback reason is recorded in `notes` |
| Basemap | map background | OpenFreeMap (positron, dark styles), no key | OSM-based, free | Documentation checked |
| Cost benchmarks | later milestones | manual | n/a | **Not collected yet** (Person B) |

Known data-quality note: the OpenCity explainer quotes 4.09 million trees, but the 17 parts are listed as 16 x 250,000 + 9,000 = about 4.009 million. The audit shows the number actually loaded.

**Freshness policy:** The scheduled GitHub Actions workflow checks the catalogue daily (03:00 UTC). It publishes the new data only if a non-bbox boundary is available and both latest satellite layers contain cloud-masked observations no older than 45 days covering at least 50% of study-area hexagons. If the source is stale, unavailable or too cloudy, the build is retained as a failed quality check rather than presenting an old or partial layer as current. These satellite layers are near-real-time observations, not continuous live sensing. The historical tree census (2019), WorldPop (2020 and 2000–2020 series) and ESA WorldCover (2020/2021) remain vintage datasets and are labelled as such.

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
