from __future__ import annotations
from pathlib import Path
import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]


def load_config(path: str | Path | None = None) -> dict:
    p = Path(path) if path else REPO_ROOT / "config" / "pilot_pune.yaml"
    with open(p, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)
