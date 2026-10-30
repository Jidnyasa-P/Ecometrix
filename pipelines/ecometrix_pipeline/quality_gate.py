"""Release checks for judge-facing data outputs.

The pipeline can still write partial diagnostics, but scheduled publication is blocked
when the study boundary is only a configured bbox or the latest satellite layers are
stale / too cloud-obscured to represent the study area.
"""
from __future__ import annotations

import argparse
import json
import math
import yaml
from datetime import date, datetime, timezone
from pathlib import Path

from .config import load_config

REQUIRED_DATA_LAYERS = (
    "osm", "worldcover", "landsat", "sentinel",
    "landsat_latest", "sentinel_latest", "population", "popseries",
)
REQUIRED_MODEL_MODULES = ("heat_model", "greenness_targets", "forecast", "need_score", "sites")
REQUIRED_AUDIT_CHECKS = ("boundary", "satellite", "latest_satellite")


def validate_manifest(manifest: dict, cfg: dict) -> list[str]:
    issues: list[str] = []
    expected_city = str(cfg.get("city_slug", ""))
    if manifest.get("city_slug") != expected_city:
        issues.append(f"Manifest city_slug {manifest.get('city_slug')!r} does not match selected city {expected_city!r}.")
    expected_currency = cfg.get("currency")
    if expected_currency and manifest.get("currency") != expected_currency:
        issues.append(f"Manifest currency {manifest.get('currency')!r} does not match selected city currency {expected_currency!r}.")
    boundary = manifest.get("boundary") or {}
    if boundary.get("fallback"):
        notes = "; ".join(boundary.get("notes") or [])
        issues.append("Study boundary is a configured bounding-box fallback" + (f": {notes}" if notes else "."))
    elif not (boundary.get("boundary_resource_id") or boundary.get("osm_ref")):
        issues.append("Boundary has no recorded source resource id or OSM reference.")
    else:
        area = boundary.get("area_km2")
        bounds = cfg.get("boundary", {}).get("area_sanity_km2", [150, 1200])
        if (not isinstance(area, (int, float)) or not math.isfinite(area)
                or not (float(bounds[0]) <= area <= float(bounds[1]))):
            issues.append(f"Boundary area {area!r} km2 is missing or outside the configured sanity range.")
        if not boundary.get("source"):
            issues.append("Boundary source provenance is missing.")

    layers = manifest.get("layers") or {}
    required_layers = list(REQUIRED_DATA_LAYERS)
    if cfg.get("tree_census", {}).get("enabled", True):
        required_layers.append("trees")
    for layer_name in required_layers:
        status = (layers.get(layer_name) or {}).get("status", "missing")
        if status != "ok":
            issues.append(f"Required data layer {layer_name} status is {status!r}, not 'ok'.")

    sat_cfg = cfg.get("satellite", {})
    max_age = int(sat_cfg.get("latest_max_age_days", 45))
    min_coverage = float(sat_cfg.get("latest_min_valid_cells_pct", 50.0))
    for layer_name in ("landsat_latest", "sentinel_latest"):
        layer = layers.get(layer_name) or {}
        if layer.get("status") != "ok":
            issues.append(f"{layer_name} layer status is {layer.get('status', 'missing')!r}, not 'ok'.")
            continue
        detail = layer.get("detail") or {}
        last = detail.get("last_observation")
        age = detail.get("age_days")
        coverage = detail.get("valid_cells_pct")
        observed_on = None
        try:
            observed_on = date.fromisoformat(str(last))
        except (TypeError, ValueError):
            issues.append(f"{layer_name} has no valid ISO last_observation date in manifest detail.")
        actual_age = ((datetime.now(timezone.utc).date() - observed_on).days
                      if observed_on is not None else None)
        if (not isinstance(age, (int, float)) or not math.isfinite(age)
                or age < 0 or age > max_age):
            issues.append(f"{layer_name} observation age {age!r} exceeds the {max_age}-day freshness limit or is invalid.")
        if actual_age is not None:
            if actual_age < 0 or actual_age > max_age:
                issues.append(f"{layer_name} observation date {last!r} is future-dated or older than {max_age} days.")
            elif isinstance(age, (int, float)) and math.isfinite(age) and abs(actual_age - age) > 1:
                issues.append(f"{layer_name} observation date {last!r} is inconsistent with age_days={age!r}.")
        if (not isinstance(coverage, (int, float)) or not math.isfinite(coverage)
                or coverage < min_coverage or coverage > 100):
            issues.append(f"{layer_name} valid-cell coverage {coverage!r}% is outside the accepted {min_coverage}-100% range.")
    return issues


def validate_outputs(manifest: dict, models: dict, audit: dict, cfg: dict) -> list[str]:
    """Check all required data and model outputs plus the key evidence checks."""
    issues = validate_manifest(manifest, cfg)
    expected_city = str(cfg.get("city_slug", ""))
    if models.get("city_slug") != expected_city:
        issues.append(f"Models manifest city_slug {models.get('city_slug')!r} does not match selected city {expected_city!r}.")
    if models.get("currency") != cfg.get("currency"):
        issues.append(f"Models manifest currency {models.get('currency')!r} does not match selected city currency {cfg.get('currency')!r}.")
    modules = models.get("modules") or {}
    required_modules = list(REQUIRED_MODEL_MODULES)
    if (Path(cfg.get("assumptions_path", "")).exists()):
        import yaml
        pack = yaml.safe_load(Path(cfg["assumptions_path"]).read_text(encoding="utf-8")) or {}
        if pack.get("finance", {}).get("enabled", True):
            required_modules.extend(("sensitivity", "portfolio"))
    for module_name in required_modules:
        status = (modules.get(module_name) or {}).get("status", "missing")
        if status != "ok":
            issues.append(f"Required model module {module_name} status is {status!r}, not 'ok'.")

    checks = {check.get("id"): check for check in audit.get("checks", [])}
    required_checks = list(REQUIRED_AUDIT_CHECKS)
    if cfg.get("tree_census", {}).get("enabled", True):
        required_checks.append("trees")
    for check_id in required_checks:
        check = checks.get(check_id)
        status = check.get("status") if check else "missing"
        if status != "pass":
            issues.append(f"Required audit check {check_id} status is {status!r}, not 'pass'.")
    return issues


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--city", default=None)
    parser.add_argument("--manifest", default=None)
    parser.add_argument("--models-manifest", default=None)
    parser.add_argument("--audit", default=None)
    parser.add_argument("--config", default=None)
    args = parser.parse_args(argv)
    cfg = load_config(args.config, city=args.city)
    out = Path(cfg["data_output"])
    paths = {"manifest": Path(args.manifest) if args.manifest else out / "manifest.json",
             "models manifest": Path(args.models_manifest) if args.models_manifest else out / "models_manifest.json",
             "audit": Path(args.audit) if args.audit else out / "audit.json"}
    release_marker = out / "release_check.json"
    # Never leave a stale passing marker after a newer build fails validation.
    release_marker.unlink(missing_ok=True)
    missing = [f"{label}: {path}" for label, path in paths.items() if not path.exists()]
    if missing:
        print("DATA QUALITY GATE FAILED: required file(s) not found: " + "; ".join(missing))
        return 1
    manifest = json.loads(paths["manifest"].read_text(encoding="utf-8"))
    models = json.loads(paths["models manifest"].read_text(encoding="utf-8"))
    audit = json.loads(paths["audit"].read_text(encoding="utf-8"))
    issues = validate_outputs(manifest, models, audit, cfg)
    if issues:
        print("DATA QUALITY GATE FAILED:")
        for issue in issues:
            print(f"- {issue}")
        return 1
    boundary = manifest["boundary"]
    marker = {
        "status": "passed",
        "city": cfg["city_slug"],
        "city_slug": cfg["city_slug"],
        "currency": cfg.get("currency"),
        "pipeline_version": manifest.get("pipeline_version"),
        "checked_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "boundary_source": boundary["source"],
        "boundary_area_km2": boundary["area_km2"],
        "required_layers": list(REQUIRED_DATA_LAYERS) + (["trees"] if cfg.get("tree_census", {}).get("enabled", True) else []),
        "required_models": list(REQUIRED_MODEL_MODULES) + (
            ["sensitivity", "portfolio"]
            if (yaml.safe_load(Path(cfg["assumptions_path"]).read_text(encoding="utf-8")) or {}).get("finance", {}).get("enabled", True)
            else []
        ),
        "required_audit_checks": list(REQUIRED_AUDIT_CHECKS) + (["trees"] if cfg.get("tree_census", {}).get("enabled", True) else []),
    }
    release_marker.parent.mkdir(parents=True, exist_ok=True)
    release_marker.write_text(json.dumps(marker, indent=2), encoding="utf-8")
    print(f"DATA QUALITY GATE PASSED: {boundary['source']}; boundary area {boundary['area_km2']} km2")
    for name in ("landsat_latest", "sentinel_latest"):
        detail = manifest["layers"][name]["detail"]
        print(f"- {name}: {detail['last_observation']} ({detail['age_days']} days old), {detail['valid_cells_pct']}% cell coverage")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
