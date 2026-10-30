"""Satellite code paths exercised with local stand-in rasters (no network). The expected values are
computed by hand in each test, so a scaling, masking or alignment bug would fail here."""
import datetime as dt
import numpy as np
import pystac
import pytest
import rasterio
from shapely.geometry import box, mapping
from ecometrix_pipeline import grid as G, satellite
from ecometrix_pipeline.config import load_config

CFG = load_config()
MINX, MINY, MAXX, MAXY = 73.80, 18.46, 73.90, 18.56


@pytest.fixture(scope="module")
def grid():
    return G.build_grid(box(73.84, 18.50, 73.86, 18.52), 9, 32643, 30)


class FakeCat:
    def __init__(self, items): self.items_ = items; self.queries = []
    def search(self, **kw):
        self.queries.append(kw)
        items = self.items_
        class S:
            def items(self): return iter(items)
        return S()


def _write(path, arr, dtype, transform):
    h, w = arr.shape
    with rasterio.open(path, "w", driver="GTiff", height=h, width=w, count=1, dtype=dtype, crs="EPSG:32643",
                       transform=transform) as d:
        d.write(arr.astype(dtype), 1)


def _item(id_, day, shape, transform, props, assets):
    it = pystac.Item(id=id_, geometry=mapping(box(MINX, MINY, MAXX, MAXY)), bbox=[MINX, MINY, MAXX, MAXY],
                     datetime=dt.datetime(2025, 4, day, 5, 0),
                     properties={**props, "proj:epsg": 32643, "proj:shape": list(shape), "proj:transform": list(transform)[:6]})
    for name, href in assets.items():
        it.add_asset(name, pystac.Asset(href=str(href), media_type="image/tiff; application=geotiff", roles=["data"],
                                        extra_fields={"raster:bands": [{"nodata": 0}]}))
    return it


def test_worldcover_shares_sum_to_100(tmp_path, grid):
    h, w = grid.shape
    gb = grid.geobox(factor=3)
    arr = np.full((h * 3, w * 3), 10, dtype="uint8"); arr[:, : w * 3 // 2] = 50
    _write(tmp_path / "wc.tif", arr, "uint8", gb.affine)
    it = _item("wc", 1, (h * 3, w * 3), gb.affine, {"esa_worldcover:version": "v200"}, {"map": tmp_path / "wc.tif"})
    r = satellite.worldcover(CFG, grid, FakeCat([it]))
    b, t = r["layers"]["builtup_pct"], r["layers"]["treecover_pct"]
    assert np.nanmax(np.abs(b + t - 100)) < 1e-6 and np.nanmin(b) == 0 and np.nanmax(b) == 100


def test_landsat_scaling_and_cloud_mask(tmp_path, grid):
    h, w = grid.shape
    def mk(id_, day, lst_c, cloud_left):
        dn = np.full((h, w), (lst_c + 273.15 - 149.0) / 0.00341802)
        qa = np.zeros((h, w)); 
        if cloud_left: qa[:, : w // 2] = 1 << 3
        _write(tmp_path / f"{id_}_st.tif", dn, "uint16", grid.transform); _write(tmp_path / f"{id_}_qa.tif", qa, "uint16", grid.transform)
        return _item(id_, day, (h, w), grid.transform, {"platform": "landsat-9", "eo:cloud_cover": 5},
                     {"lwir11": tmp_path / f"{id_}_st.tif", "qa_pixel": tmp_path / f"{id_}_qa.tif"})
    items = [mk("a", 3, 40.0, False), mk("b", 10, 44.0, True), mk("c", 19, 42.0, False)]
    r = satellite.landsat_lst(CFG, grid, FakeCat(items))
    v = r["lst_c"]
    assert np.nanmin(v) == pytest.approx(41.0, abs=0.01)     # cloudy half: median of 40 and 42
    assert np.nanmax(v) == pytest.approx(42.0, abs=0.01)     # clear half: median of 40, 44, 42
    assert r["days"] == 3
    assert r["valid_cells_pct"] == 100.0
    assert r["mean_clear_observations_per_cell"] > 0
    recent_cat = FakeCat(items)
    recent = satellite.landsat_lst(CFG, grid, recent_cat,
                                   ranges=["2025-01-01/2025-12-31"], latest=True)
    assert recent_cat.queries[0]["datetime"] == "2025-01-01/2025-12-31"
    assert recent_cat.queries[0]["query"]["eo:cloud_cover"] == {"lt": CFG["satellite"]["latest_cloud_cover_max"]}
    assert recent["valid_cells_pct"] == 100.0


def test_sentinel_ndvi_value_and_cloud_scene_ignored(tmp_path, grid):
    h, w = grid.shape; gb = grid.geobox(factor=1)
    def mk(id_, day, scl):
        for k, val, dt_ in (("b4", 3000, "uint16"), ("b8", 7000, "uint16"), ("scl", scl, "uint8")):
            _write(tmp_path / f"{id_}_{k}.tif", np.full((h, w), val), dt_, grid.transform)
        return _item(id_, day, (h, w), grid.transform, {"eo:cloud_cover": 5, "s2:processing_baseline": "05.11"},
                     {"B04": tmp_path / f"{id_}_b4.tif", "B08": tmp_path / f"{id_}_b8.tif", "SCL": tmp_path / f"{id_}_scl.tif"})
    r = satellite.sentinel_ndvi(CFG, grid, FakeCat([mk("x", 3, 4), mk("y", 8, 4), mk("z", 13, 9)]))
    # reflectance = (DN - 1000) / 10000 -> red 0.2, nir 0.6 -> NDVI 0.5
    assert np.nanmin(r["ndvi"]) == pytest.approx(0.5, abs=1e-4) and np.nanmax(r["ndvi"]) == pytest.approx(0.5, abs=1e-4)
    assert r["ndvi_nobs"].shape == (grid.n_cells,)
    assert r["valid_cells_pct"] == 100.0
    recent_cat = FakeCat([mk("recent", 18, 4)])
    recent = satellite.sentinel_ndvi(CFG, grid, recent_cat,
                                     ranges=["2025-01-01/2025-12-31"], latest=True)
    assert recent_cat.queries[0]["datetime"] == "2025-01-01/2025-12-31"
    assert recent_cat.queries[0]["query"]["eo:cloud_cover"] == {"lt": CFG["satellite"]["latest_cloud_cover_max"]}
    assert recent["valid_cells_pct"] == 100.0
