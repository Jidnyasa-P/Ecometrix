# data/

* `outputs/` : what the pipeline produces and the API serves (`cells.parquet`, `manifest.json`, `summary.json`, `audit.json`, `relationship.json`). **Committed**, so Render can serve it. It is empty until you run the "Build data" workflow or `make data`.
* `raw/` : downloads, git-ignored, recreated by the pipeline.

Nothing in this folder is hand-written or sample data. If a layer could not be built, `manifest.json` says so and the app shows the reason.
