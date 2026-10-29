from __future__ import annotations
import json
import math
from pathlib import Path
import numpy as np
import pandas as pd
from .fields import FIELDS


class DataStore:
    """Loads pipeline outputs from disk. Reloads automatically when the files change."""

    def __init__(self, data_dir: Path):
        self.dir = Path(data_dir)
        self._stamp = None
        self._cells_json: bytes | None = None
        self._meta_fields: dict | None = None
        self._df: pd.DataFrame | None = None
        self._sites: pd.DataFrame | None = None
        self._sites_json: bytes | None = None

    def _mtime(self):
        p = self.dir / "manifest.json"
        return p.stat().st_mtime if p.exists() else None

    def _refresh(self):
        def mt(n):
            p = self.dir / n
            return p.stat().st_mtime if p.exists() else None
        stamp = (mt("manifest.json"), mt("cells.parquet"), mt("analysis.parquet"), mt("sites.parquet"))
        if stamp == self._stamp:
            return
        self._stamp = stamp
        self._cells_json = self._meta_fields = self._df = self._sites = self._sites_json = None

    def json_file(self, name: str):
        p = self.dir / name
        if not p.exists():
            return None
        return json.loads(p.read_text(encoding="utf-8"))

    def manifest(self):
        return self.json_file("manifest.json")

    def df(self) -> pd.DataFrame | None:
        self._refresh()
        if self._df is None:
            p = self.dir / "cells.parquet"
            if not p.exists():
                return None
            df = pd.read_parquet(p)
            a = self.dir / "analysis.parquet"
            if a.exists():
                an = pd.read_parquet(a)
                an = an[[c for c in an.columns if c == "h3" or c not in df.columns]]
                df = df.merge(an, on="h3", how="left")
            self._df = df
        return self._df

    def sites_df(self) -> pd.DataFrame | None:
        self._refresh()
        if self._sites is None:
            p = self.dir / "sites.parquet"
            if not p.exists():
                return None
            self._sites = pd.read_parquet(p)
        return self._sites

    def site(self, site_id: str) -> dict | None:
        s = self.sites_df()
        if s is None:
            return None
        row = s[s["site_id"] == site_id]
        if row.empty:
            return None
        r = row.iloc[0].to_dict()
        return {k: (None if isinstance(v, float) and not math.isfinite(v) else v) for k, v in r.items()}

    def sites_json(self) -> bytes | None:
        s = self.sites_df()
        if s is None:
            return None
        if self._sites_json is None:
            cols = {}
            for c in s.columns:
                if c in ("site_id", "h3", "type", "verification"):
                    cols[c] = s[c].tolist()
                else:
                    cols[c] = [None if not math.isfinite(float(x)) else round(float(x), 4) for x in s[c].to_numpy(dtype=float)]
            self._sites_json = json.dumps({"n": int(len(s)), "columns": cols}, separators=(",", ":")).encode("utf-8")
        return self._sites_json

    def fields(self) -> dict:
        """Definitions for the fields present in the data, with display domains computed from the real values."""
        df = self.df()
        if df is None:
            return {}
        if self._meta_fields is None:
            out = {}
            for k, d in FIELDS.items():
                if k not in df.columns:
                    continue
                v = df[k].to_numpy(dtype=float)
                v = v[np.isfinite(v)]
                if v.size == 0:
                    continue
                scale = d.get("scale", 1)
                v = v * scale
                lo, hi = float(np.percentile(v, 2)), float(np.percentile(v, 98))
                if hi <= lo:
                    lo, hi = float(v.min()), float(v.max()) if v.max() > v.min() else float(v.min()) + 1.0
                out[k] = {**d, "key": k, "domain": [round(lo, 4), round(hi, 4)],
                          "min": round(float(v.min()), 4), "max": round(float(v.max()), 4), "n": int(v.size)}
            self._meta_fields = out
        return self._meta_fields

    def cells_json(self) -> bytes | None:
        df = self.df()
        if df is None:
            return None
        if self._cells_json is None:
            fields = self.fields()
            cols = {}
            for k, d in fields.items():
                scale = d.get("scale", 1)
                arr = (df[k].to_numpy(dtype=float) * scale)
                cols[k] = [None if not math.isfinite(x) else round(float(x), d["decimals"] + (2 if scale != 1 else 0)) for x in arr]
            payload = {"n": int(len(df)), "h3": df["h3"].tolist(), "lat": df["lat"].tolist(), "lng": df["lng"].tolist(),
                       "area_km2": df["area_km2"].tolist(), "values": cols}
            self._cells_json = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        return self._cells_json

    def cell(self, hex_id: str) -> dict | None:
        df = self.df()
        if df is None:
            return None
        row = df[df["h3"] == hex_id]
        if row.empty:
            return None
        r = row.iloc[0]
        vals = {}
        for k, d in self.fields().items():
            x = float(r[k]) * d.get("scale", 1)
            vals[k] = None if not math.isfinite(x) else round(x, d["decimals"] + (2 if d.get("scale", 1) != 1 else 0))
        return {"h3": hex_id, "lat": float(r["lat"]), "lng": float(r["lng"]), "area_km2": float(r["area_km2"]), "values": vals}
