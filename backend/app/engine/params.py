"""Load the assumptions register and draw from it. Low / base / high ranges become triangular distributions (mode = base)."""
from __future__ import annotations
from pathlib import Path
import numpy as np
import yaml

DEFAULT_PATH = Path(__file__).resolve().parents[3] / "config" / "assumptions.yaml"


def load(path: str | Path | None = None) -> dict:
    return yaml.safe_load(Path(path or DEFAULT_PATH).read_text(encoding="utf-8"))


def value(entry: dict) -> float | bool:
    return entry["value"]


def draw(entry: dict, rng: np.random.Generator, n: int, mode: str = "mc") -> np.ndarray:
    """n draws of a ranged parameter. mode='base' returns the base value (used for hand-checkable results)."""
    lo, b, hi = float(entry["low"]), float(entry["base"]), float(entry["high"])
    if mode == "base" or hi == lo:
        return np.full(n, b)
    return rng.triangular(lo, b, hi, n)


def carbon_rates(points: dict, years: int, post5_factor: np.ndarray | float, scale: np.ndarray | float) -> np.ndarray:
    """Mg C per hectare in each year 1..years, shape (draws, years). Measured points are interpolated linearly from age 0 = 0;
    after the last measured age the last rate is held and multiplied by post5_factor."""
    ages = np.array([0.0] + sorted(float(k) for k in points))
    rates = np.array([0.0] + [float(points[k]) if k in points else float(points[int(k)]) for k in sorted(points)])
    last_age, last_rate = ages[-1], rates[-1]
    yr = np.arange(1, years + 1, dtype=float)
    base = np.where(yr <= last_age, np.interp(yr, ages, rates), last_rate)
    after = yr > last_age
    scale = np.atleast_1d(scale)[:, None]
    post = np.atleast_1d(post5_factor)[:, None]
    return scale * np.where(after[None, :], base[None, :] * post, base[None, :])
