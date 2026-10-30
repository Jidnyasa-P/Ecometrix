from __future__ import annotations
import os
from pathlib import Path
import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
CONFIG_ROOT = REPO_ROOT / "config"
REGISTRY_PATH = CONFIG_ROOT / "registry.yaml"


def load_registry() -> dict:
    if not REGISTRY_PATH.exists():
        # Backwards compatibility for older source archives.
        return {"default_city": "pune", "cities": [{"slug": "pune", "name": "Pune", "country": "India",
                "currency": "INR", "locale": "en-IN", "config": "config/pilot_pune.yaml",
                "assumptions": "config/assumptions.yaml", "status": "existing_pilot"}]}
    registry = yaml.safe_load(REGISTRY_PATH.read_text(encoding="utf-8")) or {}
    cities = registry.get("cities")
    if not isinstance(cities, list) or not cities:
        raise ValueError(f"City registry is empty or invalid: {REGISTRY_PATH}")
    slugs = [str(city.get("slug", "")).strip() for city in cities]
    if any(not slug for slug in slugs) or len(slugs) != len(set(slugs)):
        raise ValueError("Every city registry entry must have a unique non-empty slug")
    return registry


def release_marker_matches_city(marker: object, city_slug: str, currency: str | None = None) -> bool:
    """A passing marker must identify the exact city and currency in its output folder."""
    return (
        isinstance(marker, dict)
        and marker.get("status") == "passed"
        and marker.get("city") == city_slug
        and marker.get("city_slug") == city_slug
        and (currency is None or marker.get("currency") == currency)
    )


def city_options() -> list[dict]:
    """Return registry metadata with build status derived from each city's own outputs."""
    registry = load_registry()
    options = []
    for entry in registry["cities"]:
        item = dict(entry)
        output = Path(item.get("data_output", f"data/cities/{item['slug']}/outputs"))
        if not output.is_absolute():
            output = REPO_ROOT / output
        release_output = output
        release_marker = release_output / "release_check.json"
        if item["slug"] == "pune" and not release_marker.exists():
            legacy_output = REPO_ROOT / "data" / "outputs"
            legacy_marker = legacy_output / "release_check.json"
            if legacy_marker.exists():
                release_output = legacy_output
                release_marker = legacy_marker
        release_passed = False
        if release_marker.exists():
            try:
                marker = yaml.safe_load(release_marker.read_text(encoding="utf-8"))
                manifest = yaml.safe_load((release_output / "manifest.json").read_text(encoding="utf-8"))
                models = yaml.safe_load((release_output / "models_manifest.json").read_text(encoding="utf-8"))
                expected_city = str(item["slug"])
                expected_currency = item.get("currency")
                release_passed = (
                    release_marker_matches_city(marker, expected_city, expected_currency)
                    and isinstance(manifest, dict)
                    and manifest.get("city_slug") == expected_city
                    and manifest.get("currency") == expected_currency
                    and isinstance(models, dict)
                    and models.get("city_slug") == expected_city
                    and models.get("currency") == expected_currency
                )
            except (OSError, yaml.YAMLError):
                release_passed = False
        if release_passed:
            item["status"] = "built"
        elif item.get("status") == "existing_pilot":
            item["status"] = "pilot_not_built"
        else:
            item["status"] = "configuration_only"
        options.append(item)
    return options


def utm_epsg_for_center(center: list[float] | tuple[float, float]) -> int:
    """Return the local UTM CRS EPSG code from a [latitude, longitude] centre."""
    lat, lon = map(float, center)
    if not (-80 <= lat <= 84) or not (-180 <= lon <= 180):
        raise ValueError(f"Centre is outside the supported UTM latitude/longitude domain: {center}")
    zone = max(1, min(60, int((lon + 180) // 6) + 1))
    return (32600 if lat >= 0 else 32700) + zone


def load_config(path: str | Path | None = None, city: str | None = None) -> dict:
    """Load one city's configuration.

    `path` remains compatible with explicit YAML file paths and old pilot_pune.yaml callers.
    Otherwise the city comes from --city/ECOMETRIX_CITY/the registry default.
    """
    selected = city or (str(path) if path and not str(path).lower().endswith((".yaml", ".yml")) else None)
    if path and str(path).lower().endswith((".yaml", ".yml")):
        p = Path(path)
        if not p.is_absolute():
            p = REPO_ROOT / p
        if not p.exists():
            raise FileNotFoundError(f"Configuration file not found: {p}")
        config_path = p
        slug = selected or p.stem.replace("pilot_", "")
    else:
        registry = load_registry()
        slug = selected or os.environ.get("ECOMETRIX_CITY") or registry.get("default_city", "pune")
        entries = {str(x["slug"]): x for x in registry["cities"]}
        if slug not in entries:
            raise ValueError(f"Unknown city '{slug}'. Available cities: {', '.join(entries)}")
        config_path = REPO_ROOT / entries[slug]["config"]
        if not config_path.exists():
            raise FileNotFoundError(f"City configuration not found for '{slug}': {config_path}")

    cfg = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    cfg["city_slug"] = cfg.get("city_slug") or slug
    cfg["utm_epsg"] = int(cfg.get("utm_epsg") or utm_epsg_for_center(cfg["center"]))
    cfg["config_path"] = str(config_path.resolve())
    assumptions_path = Path(cfg.get("assumptions_path", "config/assumptions.yaml"))
    if not assumptions_path.is_absolute():
        assumptions_path = REPO_ROOT / assumptions_path
    if not assumptions_path.exists():
        raise FileNotFoundError(f"Assumptions pack not found: {assumptions_path}")
    cfg["assumptions_path"] = str(assumptions_path.resolve())
    output = Path(cfg.get("data_output", f"data/cities/{cfg['city_slug']}/outputs"))
    if not output.is_absolute():
        output = REPO_ROOT / output
    cfg["data_output"] = str(output.resolve())
    cfg.setdefault("currency", "INR")
    cfg.setdefault("locale", "en-IN")
    cfg.setdefault("unit_system", "metric")
    cfg.setdefault("country_code", "IN")
    cfg.setdefault("country_iso3", "IND")
    return cfg
