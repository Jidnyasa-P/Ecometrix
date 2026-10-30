"""Configuration and release-identity checks; no remote data or GIS wheels required."""
from pathlib import Path

import yaml

from ecometrix_pipeline.config import (
    CONFIG_ROOT, city_options, load_config, load_registry, release_marker_matches_city,
    utm_epsg_for_center,
)
from ecometrix_pipeline.quality_gate import validate_manifest, validate_outputs


def test_registry_has_four_independent_city_profiles():
    registry = load_registry()
    entries = {entry["slug"]: entry for entry in registry["cities"]}
    assert set(entries) == {"pune", "london", "new-york", "athens"}
    configs = [load_config(city=slug) for slug in entries]
    assert len({cfg["data_output"] for cfg in configs}) == 4
    assert len({cfg["utm_epsg"] for cfg in configs}) == 4


def test_city_crs_currency_locale_and_assumptions_are_consistent():
    expected = {
        "pune": ("INR", "en-IN", 32643, True),
        "london": ("GBP", "en-GB", 32630, False),
        "new-york": ("USD", "en-US", 32618, False),
        "athens": ("EUR", "el-GR", 32634, False),
    }
    for slug, values in expected.items():
        cfg = load_config(city=slug)
        currency, locale, epsg, finance_enabled = values
        assert (cfg["currency"], cfg["locale"], cfg["utm_epsg"]) == (currency, locale, epsg)
        assert cfg["utm_epsg"] == utm_epsg_for_center(cfg["center"])
        assumptions = yaml.safe_load(Path(cfg["assumptions_path"]).read_text(encoding="utf-8"))
        assert assumptions.get("finance", {}).get("enabled", True) is finance_enabled
        assert Path(cfg["config_path"]).is_file()


def test_non_pune_cities_do_not_claim_tree_census():
    for slug in ("london", "new-york", "athens"):
        cfg = load_config(city=slug)
        assert cfg.get("tree_census", {}).get("enabled") is False
        assert "not imputed" in cfg.get("tree_census", {}).get("reason", "")


def test_release_marker_must_match_its_city():
    valid = {"status": "passed", "city": "london", "city_slug": "london", "currency": "GBP"}
    assert release_marker_matches_city(valid, "london", "GBP")
    assert not release_marker_matches_city(valid, "pune", "INR")
    assert not release_marker_matches_city(valid, "london", "USD")
    assert not release_marker_matches_city({"status": "passed", "city": "london"}, "london", "GBP")
    assert not release_marker_matches_city({"status": "failed", "city": "london", "city_slug": "london", "currency": "GBP"}, "london", "GBP")


def test_city_options_do_not_accept_stale_or_foreign_markers(tmp_path, monkeypatch):
    # Isolate the data root and place a London marker in London's folder with the wrong city.
    import ecometrix_pipeline.config as city_config
    monkeypatch.setattr(city_config, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(city_config, "REGISTRY_PATH", tmp_path / "config" / "registry.yaml")
    (tmp_path / "config").mkdir()
    (tmp_path / "config" / "registry.yaml").write_text(
        "default_city: london\ncities:\n  - slug: london\n    name: London\n    status: configuration_only\n",
        encoding="utf-8",
    )
    output = tmp_path / "data/cities/london/outputs"
    output.mkdir(parents=True)
    (output / "release_check.json").write_text(
        '{"status":"passed","city":"pune"}', encoding="utf-8"
    )
    assert city_config.city_options()[0]["status"] == "configuration_only"
    # Even a city-matching marker is not enough when its manifest pair is absent.
    (output / "release_check.json").write_text(
        '{"status":"passed","city":"london","city_slug":"london","currency":"GBP"}',
        encoding="utf-8",
    )
    assert city_config.city_options()[0]["status"] == "configuration_only"


def test_quality_gate_rejects_wrong_city_and_currency():
    cfg = load_config(city="london")
    issues = validate_manifest(
        {"city_slug": "pune", "currency": "INR", "boundary": {"fallback": True}}, cfg
    )
    assert any("city_slug" in issue for issue in issues)
    assert any("currency" in issue for issue in issues)


def test_quality_gate_accepts_only_matching_city_manifests_and_models():
    cfg = load_config(city="london")
    manifest = {
        "city_slug": "london",
        "currency": "GBP",
        "boundary": {
            "fallback": False,
            "osm_ref": "relation/65606",
            "source": "OpenStreetMap administrative boundary",
            "area_km2": 1500.0,
        },
        "layers": {
            name: {"status": "ok"} for name in (
                "osm", "worldcover", "landsat", "sentinel", "landsat_latest",
                "sentinel_latest", "population", "popseries",
            )
        },
    }
    for name in ("landsat_latest", "sentinel_latest"):
        manifest["layers"][name]["detail"] = {
            "last_observation": "2026-10-29", "age_days": 1, "valid_cells_pct": 90.0,
        }
    models = {
        "city_slug": "london",
        "currency": "GBP",
        "modules": {name: {"status": "ok"} for name in (
            "heat_model", "greenness_targets", "forecast", "need_score", "sites",
        )},
    }
    audit = {"checks": [{"id": name, "status": "pass"} for name in (
        "boundary", "satellite", "latest_satellite",
    )]}
    assert validate_outputs(manifest, models, audit, cfg) == []
    models["city_slug"] = "pune"
    assert any("Models manifest city_slug" in issue for issue in validate_outputs(manifest, models, audit, cfg))
