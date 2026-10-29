from __future__ import annotations
import os
from pathlib import Path
from fastapi import FastAPI, HTTPException, Response
from pydantic import BaseModel, Field
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from .fields import EVIDENCE
from .store import DataStore
from .engine import params as eparams, scenario as escenario

REPO_ROOT = Path(__file__).resolve().parents[2]

SOURCES = [
    {"name": "Pune Tree Census 2019", "publisher": "Pune Municipal Corporation, via OpenCity", "license": "Public domain",
     "url": "https://data.opencity.in/dataset/pune-tree-census-2019"},
    {"name": "OpenStreetMap", "publisher": "OpenStreetMap contributors", "license": "ODbL",
     "url": "https://www.openstreetmap.org/copyright"},
    {"name": "Landsat Collection 2 Level-2", "publisher": "USGS / NASA, via Microsoft Planetary Computer", "license": "Public domain",
     "url": "https://planetarycomputer.microsoft.com/dataset/landsat-c2-l2"},
    {"name": "Sentinel-2 L2A", "publisher": "ESA Copernicus, via Microsoft Planetary Computer", "license": "Free and open (Copernicus)",
     "url": "https://planetarycomputer.microsoft.com/dataset/sentinel-2-l2a"},
    {"name": "ESA WorldCover", "publisher": "ESA, via Microsoft Planetary Computer", "license": "CC BY 4.0",
     "url": "https://planetarycomputer.microsoft.com/dataset/esa-worldcover"},
    {"name": "WorldPop constrained population 2020", "publisher": "WorldPop, University of Southampton", "license": "CC BY 4.0",
     "url": "https://hub.worldpop.org/geodata/summary?id=49804"},
    {"name": "WHO green space recommendation", "publisher": "WHO Regional Office for Europe (2016 review)",
     "license": "Reference", "url": "https://www.euro.who.int/en/health-topics/environment-and-health/urban-health/publications/2016/urban-green-spaces-and-health-a-review-of-evidence-2016"},
    {"name": "Basemap tiles", "publisher": "OpenFreeMap (OpenMapTiles, OpenStreetMap)", "license": "Free, no key",
     "url": "https://openfreemap.org"},
]


class ScenarioRequest(BaseModel):
    site_id: str
    area_ha: float | None = Field(default=None, gt=0, description="Defaults to the site's estimated open land (capped by the type's maximum)")
    budget_inr: float | None = Field(default=None, ge=0)
    horizon_years: int | None = Field(default=None, ge=1, le=30)
    draws: int = Field(default=2000, ge=200, le=10000)


def create_app(data_dir: str | Path | None = None) -> FastAPI:
    data_dir = Path(data_dir or os.environ.get("DATA_DIR") or REPO_ROOT / "data" / "outputs")
    store = DataStore(data_dir)
    app = FastAPI(title="EcoMetrix API", version="0.4.0",
                  description="Serves the real baseline layers built by the EcoMetrix pipeline. No placeholder data.")
    origins = [o.strip() for o in os.environ.get("ALLOWED_ORIGINS", "").split(",") if o.strip()]
    app.add_middleware(CORSMiddleware, allow_origins=origins,
                       allow_origin_regex=os.environ.get("ALLOWED_ORIGIN_REGEX", r"https?://(localhost|127\.0\.0\.1)(:\d+)?"),
                       allow_methods=["GET", "POST"], allow_headers=["*"], max_age=3600)
    app.add_middleware(GZipMiddleware, minimum_size=1024)

    def need(obj, what: str):
        if obj is None:
            raise HTTPException(503, detail={"code": "baseline_not_built", "what": what,
                                             "hint": "Run the data pipeline (see README: 'Build the data') and redeploy."})
        return obj

    @app.get("/api/health")
    def health():
        return {"status": "ok", "data_loaded": store.manifest() is not None}

    @app.get("/api/meta")
    def meta():
        m = store.manifest()
        return {"manifest": m, "fields": list(store.fields().values()), "evidence_labels": EVIDENCE,
                "sources": SOURCES, "built": m is not None}

    @app.get("/api/summary")
    def summary():
        return need(store.json_file("summary.json"), "summary")

    @app.get("/api/audit")
    def audit():
        return need(store.json_file("audit.json"), "audit")

    @app.get("/api/relationship")
    def relationship():
        return need(store.json_file("relationship.json"), "relationship")

    @app.get("/api/cells")
    def cells():
        body = need(store.cells_json(), "cells")
        return Response(content=body, media_type="application/json", headers={"Cache-Control": "public, max-age=300"})

    @app.get("/api/forecast")
    def forecast():
        return need(store.json_file("forecast.json"), "forecast")

    @app.get("/api/model-report")
    def model_report():
        mm = store.json_file("models_manifest.json")
        return {"modules": (mm or {}).get("modules", {}) if mm else {}, "heat_model": store.json_file("heat_model.json"),
                "need": store.json_file("need_report.json"), "built": mm is not None}

    @app.get("/api/assumptions")
    def assumptions():
        return eparams.load(os.environ.get("ASSUMPTIONS_PATH"))

    @app.get("/api/sites")
    def sites():
        body = need(store.sites_json(), "sites")
        return Response(content=body, media_type="application/json", headers={"Cache-Control": "public, max-age=300"})

    @app.post("/api/scenarios/run")
    def run_scenario(req: ScenarioRequest):
        need(store.sites_df(), "sites")
        site = store.site(req.site_id)
        if site is None:
            raise HTTPException(404, detail={"code": "unknown_site"})
        try:
            return escenario.run(site, eparams.load(os.environ.get("ASSUMPTIONS_PATH")), area_ha=req.area_ha,
                                 horizon_years=req.horizon_years, budget_inr=req.budget_inr, draws=req.draws)
        except ValueError as e:
            raise HTTPException(400, detail={"code": "invalid_scenario", "message": str(e)})

    @app.get("/api/cells/{hex_id}")
    def cell(hex_id: str):
        need(store.df(), "cells")
        c = store.cell(hex_id)
        if c is None:
            raise HTTPException(404, detail={"code": "unknown_cell"})
        return c

    return app


app = create_app()
