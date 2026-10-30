"""Mapped green space from OpenStreetMap (Overpass API), classified and measured in a metric CRS.

Three classes, deliberately kept apart:
  public_green    parks, gardens, playgrounds, recreation grounds, village greens (not tagged private/no access)
  forest_reserve  forest, woodland and nature reserves (often hill reserves, access can be limited)
  open_green      grass, meadow, scrub (not counted as access to green space)
Only public_green polygons of at least the city-configured min_area_ha count toward its park-access measure.
"""
from __future__ import annotations
import numpy as np
import shapely
from shapely import STRtree
from shapely.geometry import shape
from shapely.ops import unary_union
from pyproj import Transformer
from .grid import StudyGrid, cell_polygon_utm, project

PUBLIC_LEISURE = {"park", "garden", "playground", "recreation_ground"}
PUBLIC_LANDUSE = {"village_green", "recreation_ground"}
FOREST_LANDUSE = {"forest"}
FOREST_NATURAL = {"wood"}
OPEN_LANDUSE = {"grass", "meadow"}
OPEN_NATURAL = {"grassland", "scrub"}


def build_query(bbox, timeout: int) -> str:
    w, s, e, n = bbox
    b = f"({s},{w},{n},{e})"
    return (f"[out:json][timeout:{timeout}];("
            f'nwr["leisure"~"^(park|garden|playground|recreation_ground|nature_reserve)$"]{b};'
            f'nwr["landuse"~"^(forest|village_green|recreation_ground|grass|meadow)$"]{b};'
            f'nwr["natural"~"^(wood|grassland|scrub)$"]{b};'
            f");out geom;")


def classify(tags: dict) -> str | None:
    if tags.get("access") in ("private", "no") and tags.get("leisure") in PUBLIC_LEISURE | {"nature_reserve"}:
        return None if tags.get("leisure") != "nature_reserve" else "forest_reserve"
    if tags.get("leisure") in PUBLIC_LEISURE or tags.get("landuse") in PUBLIC_LANDUSE:
        return "public_green"
    if tags.get("leisure") == "nature_reserve" or tags.get("landuse") in FOREST_LANDUSE or tags.get("natural") in FOREST_NATURAL:
        return "forest_reserve"
    if tags.get("landuse") in OPEN_LANDUSE or tags.get("natural") in OPEN_NATURAL:
        return "open_green"
    return None


def fetch_overpass(cfg: dict, bbox, sess) -> dict:
    q = build_query(bbox, cfg["osm"]["timeout_s"])
    r = sess.post(cfg["osm"]["overpass_url"], data={"data": q}, timeout=cfg["osm"]["timeout_s"] + 60)
    r.raise_for_status()
    return r.json()


def parse_overpass(data: dict, epsg: int) -> dict[str, list]:
    """Overpass JSON -> {class: [shapely polygons in metric CRS]}."""
    import osm2geojson
    fc = osm2geojson.json2geojson(data, filter_used_refs=False)
    t = Transformer.from_crs(4326, epsg, always_xy=True)
    out: dict[str, list] = {"public_green": [], "forest_reserve": [], "open_green": []}
    for f in fc.get("features", []):
        g = f.get("geometry")
        if not g or g.get("type") not in ("Polygon", "MultiPolygon"):
            continue
        cls = classify(f.get("properties", {}).get("tags", {}) or {})
        if cls is None:
            continue
        geom = shapely.make_valid(shape(g))
        geom = project(geom, t)
        for part in getattr(geom, "geoms", [geom]):
            if part.geom_type == "Polygon" and part.area > 0:
                out[cls].append(part)
    return out


def dissolve(polys: list):
    return unary_union(polys) if polys else None


def nearest_distance_m(points_xy: np.ndarray, polys: list) -> np.ndarray:
    """Distance (m) from each point to the nearest polygon edge/interior (0 inside). inf if no polygons."""
    if not polys or len(points_xy) == 0:
        return np.full(len(points_xy), np.inf)
    tree = STRtree(polys)
    pts = shapely.points(points_xy[:, 0], points_xy[:, 1])
    idx, dist = tree.query_nearest(pts, return_distance=True, all_matches=False)
    out = np.full(len(points_xy), np.inf)
    out[idx[0]] = dist
    return out


def area_per_cell_ha(grid: StudyGrid, polys: list) -> np.ndarray:
    """Hectares of the dissolved polygons inside each H3 cell."""
    res = np.zeros(grid.n_cells)
    geom = dissolve(polys)
    if geom is None or geom.is_empty:
        return res
    parts = list(getattr(geom, "geoms", [geom]))
    tree = STRtree(parts)
    for i, c in enumerate(grid.cells):
        cp = cell_polygon_utm(int(c), grid.to_utm)
        cand = tree.query(cp)
        if len(cand) == 0:
            continue
        inter = cp.intersection(unary_union([parts[j] for j in cand]))
        res[i] = inter.area / 10_000.0
    return res


def summarize(polys_by_class: dict[str, list], min_area_ha: float) -> dict:
    pub = polys_by_class["public_green"]
    qual = [p for p in pub if p.area / 10_000.0 >= min_area_ha]
    return {"public_green_polygons": len(pub), "public_green_qualifying_polygons": len(qual),
            "public_green_total_ha": round(sum(p.area for p in pub) / 10_000.0, 1),
            "public_green_qualifying_ha": round(sum(p.area for p in qual) / 10_000.0, 1),
            "forest_reserve_polygons": len(polys_by_class["forest_reserve"]),
            "open_green_polygons": len(polys_by_class["open_green"])}
