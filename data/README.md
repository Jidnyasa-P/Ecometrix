# City data folders

Each city has an isolated folder:

```text
data/cities/<city-slug>/raw/       # downloaded source files (git-ignored)
data/cities/<city-slug>/outputs/  # manifest, layers, parquet, audit and models
```

Configured slugs: `pune`, `london`, `new-york`, `athens`. Outputs are not shared between cities. A `release_check.json` is written only after the city-specific data, core model and audit checks pass. The website marks a city built only when that marker exists and has `status: passed`.

`data/outputs/` is retained as a legacy Pune path for compatibility with older local builds. New builds write to `data/cities/pune/outputs/`.
