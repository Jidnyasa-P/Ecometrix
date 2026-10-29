"""Study-area boundary. Primary: OpenStreetMap polygon via Nominatim. Fallback: configured bounding box.

The source actually used is recorded so the audit page can show it; the fallback is never silent.
"""
from __future__ import annotations
from shapely.geometry import shape, box, Point
from .grid import project
from pyproj import Transformer


def area_km2(geom, epsg: int) -> float:
    t = Transformer.from_crs(4326, epsg, always_xy=True)
    return project(geom, t).area / 1e6


def _validate(geom, cfg) -> tuple[bool, str]:
    if geom.geom_type not in ("Polygon", "MultiPolygon"):
        return False, f"geometry type {geom.geom_type}"
    lat, lon = cfg["center"]
    if not geom.buffer(0).contains(Point(lon, lat)):
        return False, "polygon does not contain the city centre point"
    a = area_km2(geom, cfg["utm_epsg"])
    lo, hi = cfg["boundary"]["area_sanity_km2"]
    if not (lo <= a <= hi):
        return False, f"area {a:.0f} km2 outside sanity range {lo}-{hi}"
    return True, f"{a:.1f} km2"


def fetch_boundary(cfg: dict, sess) -> dict:
    b = cfg["boundary"]
    notes: list[str] = []
    try:
        r = sess.get(b["nominatim_url"], params={
            "q": b["query"], "format": "jsonv2", "polygon_geojson": 1, "limit": 8, "countrycodes": "in"},
            timeout=60)
        r.raise_for_status()
        for hit in r.json():
            if hit.get("category", hit.get("class")) != "boundary":
                continue
            geom = shape(hit["geojson"]).buffer(0)
            ok, why = _validate(geom, cfg)
            if ok:
                return {"geometry": geom, "source": "OpenStreetMap boundary via Nominatim",
                        "osm_ref": f"{hit.get('osm_type')}/{hit.get('osm_id')}", "name": hit.get("display_name"),
                        "area_km2": round(area_km2(geom, cfg["utm_epsg"]), 1), "fallback": False, "notes": notes}
            notes.append(f"rejected {hit.get('display_name')}: {why}")
    except Exception as e:  # network or parsing problem
        notes.append(f"Nominatim lookup failed: {e!r}")
    w, s, e_, n = cfg["fallback_bbox"]
    geom = box(w, s, e_, n)
    return {"geometry": geom, "source": "Configured bounding box (FALLBACK, not an official boundary)",
            "osm_ref": None, "name": cfg["city"], "area_km2": round(area_km2(geom, cfg["utm_epsg"]), 1),
            "fallback": True, "notes": notes}
