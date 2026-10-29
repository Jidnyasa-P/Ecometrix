"""Pune Tree Census 2019 (PMC open data, mirrored on OpenCity, public domain): stream every part and
count trees per H3 cell. Nothing is sampled: every row is read."""
from __future__ import annotations
import re
import tempfile
from collections import Counter
from pathlib import Path
import numpy as np
import pandas as pd
from .grid import StudyGrid, latlng_to_cells

_PAIR = re.compile(r"(-?\d{1,3}\.\d+)[\s,;|]+(-?\d{1,3}\.\d+)")


def list_resources(cfg: dict, sess) -> list[dict]:
    tc = cfg["tree_census"]
    r = sess.get(f"{tc['ckan_base']}/api/3/action/package_show", params={"id": tc["package_id"]}, timeout=60)
    r.raise_for_status()
    res = r.json()["result"]["resources"]
    res = [x for x in res if str(x.get("format", "")).lower() == "csv" and x.get("url")]
    return sorted(res, key=lambda x: x.get("position", 0))


def _in_range(lat, lon, center) -> tuple[np.ndarray, np.ndarray]:
    """Boolean masks for plausible values near the city (guards against swapped or projected columns)."""
    clat, clon = center
    return (np.abs(lat - clat) < 0.75), (np.abs(lon - clon) < 0.75)


def extract_lat_lon(df: pd.DataFrame, center) -> tuple[np.ndarray, np.ndarray, str]:
    """Find latitude/longitude in a chunk. Handles separate columns or a combined 'geo-location' column."""
    cols = {c: str(c).strip().lower() for c in df.columns}
    lat_c = next((c for c, n in cols.items() if re.fullmatch(r"(lat|latitude|lat_dd|gps_lat|y|ycoord|y_coord)", n)), None)
    lon_c = next((c for c, n in cols.items() if re.fullmatch(r"(lon|lng|long|longitude|lon_dd|gps_lon|x|xcoord|x_coord)", n)), None)
    if lat_c is not None and lon_c is not None:
        lat = pd.to_numeric(df[lat_c], errors="coerce").to_numpy(float)
        lon = pd.to_numeric(df[lon_c], errors="coerce").to_numpy(float)
        return lat, lon, f"columns '{lat_c}' / '{lon_c}'"
    for c, n in cols.items():
        if any(k in n for k in ("geo", "location", "coord", "latlon", "lat_lon", "geometry")):
            ex = df[c].astype(str).str.extract(_PAIR)
            a = pd.to_numeric(ex[0], errors="coerce").to_numpy(float)
            b = pd.to_numeric(ex[1], errors="coerce").to_numpy(float)
            clat, clon = center
            # decide which element is latitude by proximity to the city centre
            swap = np.nanmedian(np.abs(a - clon)) < np.nanmedian(np.abs(a - clat))
            lat, lon = (b, a) if swap else (a, b)
            return lat, lon, f"combined column '{c}' ({'lon,lat' if swap else 'lat,lon'})"
    raise ValueError(f"No latitude/longitude columns found. Columns: {list(df.columns)}")


def _species_col(df: pd.DataFrame) -> str | None:
    for c in df.columns:
        n = str(c).lower()
        if "botanical" in n or "species" in n or "scientific" in n:
            return c
    for c in df.columns:
        if "common" in str(c).lower() or "local" in str(c).lower():
            return c
    return None


def count_trees(cfg: dict, grid: StudyGrid, sess, workdir: Path | None = None, files: list[Path] | None = None) -> dict:
    """Return per-cell counts and audit statistics. `files` lets tests inject local CSVs."""
    center = tuple(cfg["center"])
    counts: dict[int, int] = {}
    rows_total = rows_valid = rows_inside = 0
    species = Counter()
    detected = set()
    species_name = None
    parts = []
    srcs: list[tuple[str, Path | str]] = []
    if files is not None:
        srcs = [(f.name, f) for f in files]
    else:
        resources = list_resources(cfg, sess)
        parts = [{"name": r.get("name"), "size": r.get("size")} for r in resources]
        tmpdir = Path(workdir or tempfile.mkdtemp(prefix="trees_"))
        tmpdir.mkdir(parents=True, exist_ok=True)
        for r in resources:
            path = tmpdir / f"{r['id']}.csv"
            with sess.get(r["url"], stream=True, timeout=300) as resp:
                resp.raise_for_status()
                with open(path, "wb") as f:
                    for chunk in resp.iter_content(1 << 20):
                        f.write(chunk)
            srcs.append((r.get("name") or path.name, path))
    cell_set = pd.Index(grid.cells)
    for name, path in srcs:
        for chunk in pd.read_csv(path, chunksize=200_000, low_memory=False, encoding_errors="replace"):
            lat, lon, how = extract_lat_lon(chunk, center)
            detected.add(how)
            n = len(chunk)
            rows_total += n
            la_ok, lo_ok = _in_range(lat, lon, center)
            valid = np.isfinite(lat) & np.isfinite(lon) & la_ok & lo_ok
            rows_valid += int(valid.sum())
            if not valid.any():
                continue
            ids = latlng_to_cells(lat[valid], lon[valid], grid.res)
            keep = cell_set.get_indexer(ids) >= 0
            rows_inside += int(keep.sum())
            u, c = np.unique(ids[keep], return_counts=True)
            for k, v in zip(u.tolist(), c.tolist()):
                counts[k] = counts.get(k, 0) + v
            sc = _species_col(chunk)
            if sc is not None:
                species_name = sc
                vals = chunk.loc[valid, sc].astype(str).str.strip()
                species.update(vals[keep].tolist())
    per_cell = np.array([counts.get(int(c), 0) for c in grid.cells], dtype=float)
    top = []
    if species:
        tot = sum(species.values())
        top = [{"species": k, "trees": v, "share": round(v / tot, 4)} for k, v in species.most_common(5)]
    return {"per_cell": per_cell, "rows_total": rows_total, "rows_valid_coords": rows_valid,
            "rows_inside_study_area": rows_inside, "parts": parts, "n_parts_read": len(srcs),
            "coordinate_detection": sorted(detected), "species_column": species_name,
            "species_distinct": len(species), "species_top": top}
