"""Study-area boundary from the 2025 PMC electoral wards, then OSM, then a flagged bbox.

The preferred source is the 2025 41-ward KML published in OpenCity's PMC Wards Info
catalogue and credited to Parisar. Ward polygons are dissolved into the city outline and
checked against the expanded PMC area. The OSM Nominatim lookup is secondary; the
configured rectangle is the last resort and is always explicitly marked as a fallback.
"""
from __future__ import annotations

from xml.etree import ElementTree as ET

from shapely.geometry import shape, box, Point, Polygon
from shapely.ops import unary_union
from .grid import project
from pyproj import Transformer


def area_km2(geom, epsg: int) -> float:
    t = Transformer.from_crs(4326, epsg, always_xy=True)
    return project(geom, t).area / 1e6


def _polygon_parts(geom):
    """Return polygon components only; discard non-area geometry from mixed collections."""
    if geom.is_empty:
        return []
    if geom.geom_type == "Polygon":
        return [geom]
    if geom.geom_type == "MultiPolygon":
        return list(geom.geoms)
    if geom.geom_type == "GeometryCollection":
        return [part for child in geom.geoms for part in _polygon_parts(child)]
    return []


def _geojson_polygons(payload: dict):
    """Parse a GeoJSON FeatureCollection, Feature, or bare Polygon/MultiPolygon."""
    if not isinstance(payload, dict):
        raise ValueError("boundary resource is not a GeoJSON object")
    kind = payload.get("type")
    if kind == "FeatureCollection":
        features = payload.get("features") or []
        raw_geometries = [feature.get("geometry") for feature in features if feature.get("geometry")]
    elif kind == "Feature":
        raw_geometries = [payload.get("geometry")] if payload.get("geometry") else []
    elif kind in ("Polygon", "MultiPolygon", "GeometryCollection"):
        raw_geometries = [payload]
    else:
        raise ValueError(f"unsupported GeoJSON type: {kind!r}")

    polygons = []
    for raw in raw_geometries:
        polygons.extend(_polygon_parts(shape(raw)))
    if not polygons:
        raise ValueError("boundary GeoJSON contains no polygon features")
    merged = unary_union(polygons)
    if not merged.is_valid:
        merged = merged.buffer(0)
    if merged.geom_type not in ("Polygon", "MultiPolygon") or merged.is_empty:
        raise ValueError(f"dissolved boundary is not polygonal: {merged.geom_type}")
    return merged, len(raw_geometries)


def _kml_coordinates(text: str) -> list[tuple[float, float]]:
    coords = []
    for token in (text or "").replace("\n", " ").split():
        parts = token.split(",")
        if len(parts) < 2:
            continue
        coords.append((float(parts[0]), float(parts[1])))
    if len(coords) < 4:
        raise ValueError("KML polygon ring has fewer than four coordinate pairs")
    return coords


def _kml_polygons(content: bytes | str) -> tuple[object, int]:
    """Parse KML ward Placemarks, preserving holes and dissolving their polygons."""
    if isinstance(content, bytes):
        content = content.decode("utf-8-sig")
    root = ET.fromstring(content)

    def local_name(element):
        return element.tag.rsplit("}", 1)[-1]

    placemark_count = 0
    polygons = []
    for placemark in (node for node in root.iter() if local_name(node) == "Placemark"):
        placemark_polygons = []
        for polygon_node in (node for node in placemark.iter() if local_name(node) == "Polygon"):
            outer = None
            holes = []
            for boundary_node in polygon_node:
                boundary_kind = local_name(boundary_node)
                if boundary_kind not in {"outerBoundaryIs", "innerBoundaryIs"}:
                    continue
                ring_node = next((node for node in boundary_node.iter() if local_name(node) == "coordinates"), None)
                if ring_node is None or not ring_node.text:
                    continue
                ring = _kml_coordinates(ring_node.text)
                if boundary_kind == "outerBoundaryIs":
                    outer = ring
                else:
                    holes.append(ring)
            if outer:
                poly = Polygon(outer, holes)
                if not poly.is_empty and poly.area > 0:
                    placemark_polygons.append(poly)
        if placemark_polygons:
            placemark_count += 1
            polygons.extend(placemark_polygons)

    if not polygons:
        raise ValueError("KML resource contains no polygon Placemarks")
    merged = unary_union(polygons)
    if not merged.is_valid:
        merged = merged.buffer(0)
    if merged.geom_type not in ("Polygon", "MultiPolygon") or merged.is_empty:
        raise ValueError(f"dissolved KML boundary is not polygonal: {merged.geom_type}")
    return merged, placemark_count


def _validate(geom, cfg) -> tuple[bool, str]:
    if geom.geom_type not in ("Polygon", "MultiPolygon"):
        return False, f"geometry type {geom.geom_type}"
    if geom.is_empty or not geom.is_valid:
        return False, "geometry is empty or invalid"
    lat, lon = cfg["center"]
    if not geom.buffer(0).covers(Point(lon, lat)):
        return False, "polygon does not cover the city centre point"
    a = area_km2(geom, cfg["utm_epsg"])
    lo, hi = cfg["boundary"]["area_sanity_km2"]
    if not (lo <= a <= hi):
        return False, f"area {a:.1f} km2 outside sanity range {lo}-{hi}"
    return True, f"{a:.1f} km2"


def _open_city_ward_boundary(cfg: dict, sess) -> dict:
    """Load and dissolve the configured current PMC electoral-ward resource."""
    b = cfg["boundary"]
    base = b["opencity_ckan_base"].rstrip("/")
    package_id = b["opencity_package_id"]
    response = sess.get(f"{base}/api/3/action/package_show", params={"id": package_id}, timeout=60)
    response.raise_for_status()
    package = response.json().get("result")
    if not isinstance(package, dict):
        raise ValueError("OpenCity CKAN package_show returned no result object")

    target = " ".join(str(b["opencity_resource_name"]).casefold().split())
    target_format = str(b.get("opencity_resource_format", "GeoJSON")).strip().casefold()
    candidates = []
    for resource in package.get("resources", []):
        fmt = str(resource.get("format", "")).strip().casefold()
        name = " ".join(str(resource.get("name", "")).casefold().split())
        if fmt == target_format and name == target and resource.get("url"):
            candidates.append(resource)

    if len(candidates) != 1:
        available = [f"{r.get('name')} ({r.get('format')})" for r in package.get("resources", [])]
        raise ValueError(
            f"expected one {target_format} resource named {b['opencity_resource_name']!r}; "
            f"found {len(candidates)}. Available resources: {available[:12]}"
        )

    resource = candidates[0]
    data_response = sess.get(resource["url"], timeout=120)
    data_response.raise_for_status()
    if target_format in {"kml", "kmz"}:
        if target_format == "kmz":
            raise ValueError("KMZ is not supported; configure the uncompressed KML resource")
        content = getattr(data_response, "content", None)
        if not content:
            content = getattr(data_response, "text", "")
        geom, feature_count = _kml_polygons(content)
    else:
        payload = data_response.json()
        geom, feature_count = _geojson_polygons(payload)

    min_features = int(b.get("min_ward_features", 5))
    if feature_count < min_features:
        raise ValueError(f"expected at least {min_features} ward features, found {feature_count}")
    ok, why = _validate(geom, cfg)
    if not ok:
        raise ValueError(f"2025 PMC electoral-ward boundary rejected: {why}")

    credit = (resource.get("credit") or resource.get("author") or package.get("author")
              or "OpenCity catalogue (resource credit not specified)")
    package_modified = package.get("metadata_modified") or package.get("metadata_created")
    resource_modified = resource.get("last_modified") or resource.get("metadata_modified")
    return {
        "geometry": geom,
        "source": "PMC Electoral Wards 2025 (41 wards; OpenCity resource credited to Parisar)",
        "osm_ref": None,
        "name": "Pune Municipal Corporation",
        "area_km2": round(area_km2(geom, cfg["utm_epsg"]), 1),
        "fallback": False,
        "boundary_dataset": package_id,
        "boundary_dataset_url": "https://data.opencity.in/dataset/pune-wards-info",
        "boundary_resource_id": resource.get("id"),
        "boundary_resource_name": resource.get("name"),
        "boundary_resource_format": resource.get("format"),
        "boundary_resource_credit": credit,
        "boundary_metadata_modified": package_modified,
        "boundary_resource_modified": resource_modified,
        "boundary_ward_features": feature_count,
        "notes": [],
    }


def _nominatim_boundary(cfg: dict, sess, notes: list[str]) -> dict | None:
    b = cfg["boundary"]
    queries = b.get("nominatim_queries") or [b["query"]]
    for query in queries:
        try:
            r = sess.get(b["nominatim_url"], params={
                "q": query, "format": "jsonv2", "polygon_geojson": 1, "limit": 10,
                "countrycodes": "in", "addressdetails": 1,
            }, timeout=60)
            r.raise_for_status()
            hits = r.json()
            if not hits:
                notes.append(f"Nominatim returned no candidates for query {query!r}.")
                continue
            accepted_type = False
            for hit in hits:
                category = hit.get("category", hit.get("class"))
                if category != "boundary" or not hit.get("geojson"):
                    notes.append(
                        f"Nominatim candidate skipped for {query!r}: "
                        f"category={category!r}, name={hit.get('display_name', 'unknown')!r}."
                    )
                    continue
                accepted_type = True
                try:
                    geom = shape(hit["geojson"]).buffer(0)
                except Exception as exc:
                    notes.append(f"Nominatim geometry parse failed for {hit.get('display_name')!r}: {exc!r}")
                    continue
                ok, why = _validate(geom, cfg)
                if ok:
                    return {
                        "geometry": geom,
                        "source": "OpenStreetMap administrative boundary via Nominatim",
                        "osm_ref": f"{hit.get('osm_type')}/{hit.get('osm_id')}",
                        "name": hit.get("display_name"),
                        "area_km2": round(area_km2(geom, cfg["utm_epsg"]), 1),
                        "fallback": False,
                        "notes": notes,
                    }
                notes.append(f"Nominatim boundary rejected for {hit.get('display_name')!r}: {why}.")
            if not accepted_type:
                notes.append(f"Nominatim returned candidates for {query!r}, but none was tagged as a boundary.")
        except Exception as exc:
            notes.append(f"Nominatim lookup failed for {query!r}: {type(exc).__name__}: {exc}")
    return None


def fetch_boundary(cfg: dict, sess) -> dict:
    """Try the current PMC ward dataset, then OSM, then a transparent rectangle fallback."""
    notes: list[str] = []
    try:
        return _open_city_ward_boundary(cfg, sess)
    except Exception as exc:
        notes.append(f"OpenCity PMC ward boundary unavailable: {type(exc).__name__}: {exc}")

    osm_result = _nominatim_boundary(cfg, sess, notes)
    if osm_result is not None:
        return osm_result

    w, s, e_, n = cfg["fallback_bbox"]
    geom = box(w, s, e_, n)
    return {
        "geometry": geom,
        "source": "Configured bounding box (FALLBACK, not an official boundary)",
        "osm_ref": None,
        "name": cfg["city"],
        "area_km2": round(area_km2(geom, cfg["utm_epsg"]), 1),
        "fallback": True,
        "notes": notes or ["No configured boundary source returned a valid polygon."],
    }
