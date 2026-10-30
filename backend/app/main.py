from __future__ import annotations
import os
import sys
from pathlib import Path
from fastapi import FastAPI, HTTPException, Response, Query
from pydantic import BaseModel, Field
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from .fields import EVIDENCE
from .store import DataStore
from .engine import scenario as escenario

REPO_ROOT = Path(__file__).resolve().parents[2]
PIPELINES_DIR = REPO_ROOT / "pipelines"
if str(PIPELINES_DIR) not in sys.path:
    sys.path.insert(0, str(PIPELINES_DIR))
from ecometrix_pipeline.config import load_config, city_options, load_registry  # noqa: E402

BASE_SOURCES = [
    {"name": "OpenStreetMap", "publisher": "OpenStreetMap contributors", "license": "ODbL",
     "url": "https://www.openstreetmap.org/copyright"},
    {"name": "Landsat Collection 2 Level-2", "publisher": "USGS / NASA, via Microsoft Planetary Computer", "license": "Public domain",
     "url": "https://planetarycomputer.microsoft.com/dataset/landsat-c2-l2"},
    {"name": "Sentinel-2 L2A", "publisher": "ESA Copernicus, via Microsoft Planetary Computer", "license": "Free and open (Copernicus)",
     "url": "https://planetarycomputer.microsoft.com/dataset/sentinel-2-l2a"},
    {"name": "ESA WorldCover", "publisher": "ESA, via Microsoft Planetary Computer", "license": "CC BY 4.0",
     "url": "https://planetarycomputer.microsoft.com/dataset/esa-worldcover"},
    {"name": "WorldPop population data", "publisher": "WorldPop, University of Southampton", "license": "CC BY 4.0",
     "url": "https://hub.worldpop.org/project/categories?id=3"},
    {"name": "Basemap tiles", "publisher": "OpenFreeMap (OpenMapTiles, OpenStreetMap)", "license": "Free, no key",
     "url": "https://openfreemap.org"},
]


class ScenarioRequest(BaseModel):
    site_id: str
    area_ha: float | None = Field(default=None, gt=0, description="Defaults to the site's estimated open land")
    budget_amount: float | None = Field(default=None, ge=0, description="Optional budget in the selected city's currency")
    # Legacy Pune API key retained for older clients.
    budget_inr: float | None = Field(default=None, ge=0, description="Deprecated; use budget_amount")
    horizon_years: int | None = Field(default=None, ge=1, le=30)
    draws: int = Field(default=2000, ge=200, le=10000)


def create_app(data_dir: str | Path | None = None) -> FastAPI:
    fixed_data_dir = Path(data_dir or os.environ["DATA_DIR"]) if data_dir or os.environ.get("DATA_DIR") else None
    stores: dict[str, DataStore] = {}

    def get_city_context(city_slug: str | None):
        try:
            cfg = load_config(city=city_slug)
        except (ValueError, FileNotFoundError) as exc:
            raise HTTPException(404, detail={"code": "unknown_city", "message": str(exc)}) from exc
        slug = cfg["city_slug"]
        if slug not in stores:
            path = fixed_data_dir or Path(cfg["data_output"])
            # Backward-compatible location for the existing Pune pilot archive.
            if fixed_data_dir is None and slug == "pune" and not path.exists() and (REPO_ROOT / "data" / "outputs").exists():
                path = REPO_ROOT / "data" / "outputs"
            stores[slug] = DataStore(path)
        return cfg, stores[slug]

    app = FastAPI(title="EcoMetrix API", version="0.5.0",
                  description="Multi-city urban greening evidence platform. Each city is served only from its own built data folder.")
    origins = [o.strip() for o in os.environ.get("ALLOWED_ORIGINS", "").split(",") if o.strip()]
    app.add_middleware(CORSMiddleware, allow_origins=origins,
                       allow_origin_regex=os.environ.get("ALLOWED_ORIGIN_REGEX", r"https?://(localhost|127\.0\.0\.1)(:\d+)?"),
                       allow_methods=["GET", "POST"], allow_headers=["*"], max_age=3600)
    app.add_middleware(GZipMiddleware, minimum_size=1024)

    def need(obj, what: str):
        if obj is None:
            raise HTTPException(503, detail={"code": "baseline_not_built", "what": what,
                                             "hint": "This city has not been built yet. Run its data pipeline and model build; see README."})
        return obj

    @app.get("/api/health")
    def health(city: str | None = Query(default=None)):
        cfg, store = get_city_context(city)
        return {"status": "ok", "city": cfg["city_slug"], "data_loaded": store.manifest() is not None}

    @app.get("/api/cities")
    def cities():
        return {"default_city": load_registry().get("default_city", "pune"), "cities": city_options()}

    @app.get("/api/meta")
    def meta(city: str | None = Query(default=None)):
        cfg, store = get_city_context(city)
        m = store.manifest()
        # A city is selectable as a completed build only after its data/model quality gate passed.
        release_check = store.json_file("release_check.json")
        models_manifest = store.json_file("models_manifest.json")
        sources = list(BASE_SOURCES)
        tree_cfg = cfg.get("tree_census", {})
        if tree_cfg.get("enabled") and tree_cfg.get("source"):
            sources.insert(0, {"name": "City tree inventory", "publisher": tree_cfg.get("publisher", cfg.get("city")),
                               "license": tree_cfg.get("license", "See source"), "url": tree_cfg["source"]})
        assumptions = Path(cfg["assumptions_path"])
        if os.environ.get("ASSUMPTIONS_PATH") and cfg["city_slug"] == "pune":
            assumptions = Path(os.environ["ASSUMPTIONS_PATH"])
        import yaml
        pack = yaml.safe_load(assumptions.read_text(encoding="utf-8")) or {}
        city_info = {"slug": cfg["city_slug"], "name": cfg["city"], "country": cfg.get("country"),
                     "country_code": cfg.get("country_code"), "currency": cfg.get("currency", "INR"),
                     "locale": cfg.get("locale", "en-IN"), "unit_system": cfg.get("unit_system", "metric"),
                     "access": cfg.get("access", {}), "finance_enabled": pack.get("finance", {}).get("enabled", True),
                     "finance_reason": pack.get("finance", {}).get("reason")}
        built = bool(
            isinstance(m, dict)
            and m.get("city_slug") == cfg["city_slug"]
            and m.get("currency") == cfg.get("currency")
            and isinstance(models_manifest, dict)
            and models_manifest.get("city_slug") == cfg["city_slug"]
            and models_manifest.get("currency") == cfg.get("currency")
            and isinstance(release_check, dict)
            and release_check.get("status") == "passed"
            and release_check.get("city") == cfg["city_slug"]
            and release_check.get("city_slug") == cfg["city_slug"]
            and release_check.get("currency") == cfg.get("currency")
        )
        return {"manifest": m, "fields": list(store.fields().values()), "evidence_labels": EVIDENCE,
                "sources": sources, "built": built, "city": city_info, "cities": city_options()}

    @app.get("/api/summary")
    def summary(city: str | None = Query(default=None)):
        _, store = get_city_context(city)
        return need(store.json_file("summary.json"), "summary")

    @app.get("/api/audit")
    def audit(city: str | None = Query(default=None)):
        _, store = get_city_context(city)
        return need(store.json_file("audit.json"), "audit")

    @app.get("/api/relationship")
    def relationship(city: str | None = Query(default=None)):
        _, store = get_city_context(city)
        return need(store.json_file("relationship.json"), "relationship")

    @app.get("/api/cells")
    def cells(city: str | None = Query(default=None)):
        _, store = get_city_context(city)
        body = need(store.cells_json(), "cells")
        return Response(content=body, media_type="application/json", headers={"Cache-Control": "public, max-age=300"})

    @app.get("/api/forecast")
    def forecast(city: str | None = Query(default=None)):
        _, store = get_city_context(city)
        return need(store.json_file("forecast.json"), "forecast")

    @app.get("/api/portfolios")
    def portfolios(city: str | None = Query(default=None)):
        _, store = get_city_context(city)
        return need(store.json_file("portfolios.json"), "portfolios")

    @app.get("/api/sensitivity")
    def sensitivity(city: str | None = Query(default=None)):
        _, store = get_city_context(city)
        return need(store.json_file("sensitivity.json"), "sensitivity")

    @app.get("/api/model-report")
    def model_report(city: str | None = Query(default=None)):
        _, store = get_city_context(city)
        mm = store.json_file("models_manifest.json")
        return {"modules": (mm or {}).get("modules", {}) if mm else {}, "heat_model": store.json_file("heat_model.json"),
                "need": store.json_file("need_report.json"), "built": mm is not None}

    @app.get("/api/assumptions")
    def assumptions(city: str | None = Query(default=None)):
        cfg, _ = get_city_context(city)
        p = Path(os.environ["ASSUMPTIONS_PATH"]) if os.environ.get("ASSUMPTIONS_PATH") and cfg["city_slug"] == "pune" else Path(cfg["assumptions_path"])
        import yaml
        return yaml.safe_load(p.read_text(encoding="utf-8")) or {}

    @app.get("/api/sites")
    def sites(city: str | None = Query(default=None)):
        _, store = get_city_context(city)
        body = need(store.sites_json(), "sites")
        return Response(content=body, media_type="application/json", headers={"Cache-Control": "public, max-age=300"})

    @app.post("/api/scenarios/run")
    def run_scenario(req: ScenarioRequest, city: str | None = Query(default=None)):
        cfg, store = get_city_context(city)
        assumptions_path = Path(os.environ["ASSUMPTIONS_PATH"]) if os.environ.get("ASSUMPTIONS_PATH") and cfg["city_slug"] == "pune" else Path(cfg["assumptions_path"])
        import yaml
        pack = yaml.safe_load(assumptions_path.read_text(encoding="utf-8")) or {}
        if not pack.get("finance", {}).get("enabled", True):
            raise HTTPException(409, detail={"code": "finance_not_configured", "message": pack.get("finance", {}).get("reason", "Local financial assumptions are not validated for this city.")})
        # Access thresholds belong to the city profile, not the shared finance pack.
        pack["access"] = cfg.get("access", {})
        need(store.sites_df(), "sites")
        site = store.site(req.site_id)
        if site is None:
            raise HTTPException(404, detail={"code": "unknown_site"})
        try:
            budget = req.budget_amount if req.budget_amount is not None else req.budget_inr
            return escenario.run(site, pack, area_ha=req.area_ha, horizon_years=req.horizon_years,
                                 budget_inr=budget, draws=req.draws)
        except ValueError as exc:
            raise HTTPException(400, detail={"code": "invalid_scenario", "message": str(exc)}) from exc

    @app.get("/api/cells/{hex_id}")
    def cell(hex_id: str, city: str | None = Query(default=None)):
        _, store = get_city_context(city)
        need(store.df(), "cells")
        result = store.cell(hex_id)
        if result is None:
            raise HTTPException(404, detail={"code": "unknown_cell"})
        return result

    return app


app = create_app()
