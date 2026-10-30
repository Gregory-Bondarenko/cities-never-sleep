import json

import numpy as np
import rasterio
from rasterio.transform import from_origin

from citiesneversleep.export_lightmap import DISPLAY_MAX, block_max, build_lightmap, to_uint8


def test_block_max_keeps_small_bright_spot():
    data = np.zeros((20, 20), dtype="float32")
    data[3, 17] = 50.0
    data[15, 2] = np.nan
    out = block_max(data, 10)
    assert out.shape == (2, 2)
    assert out[0, 1] == 50.0 and out[1, 0] == 0.0


def test_to_uint8_scale():
    v = to_uint8(np.array([0.0, DISPLAY_MAX, 10 * DISPLAY_MAX]))
    assert v.tolist() == [0, 255, 255]


def test_build_lightmap(tmp_path):
    data = np.zeros((40, 60), dtype="float32")
    data[5, 5] = 100.0
    profile = {
        "driver": "GTiff",
        "height": 40,
        "width": 60,
        "count": 1,
        "dtype": "float32",
        "crs": "EPSG:4326",
        "transform": from_origin(19.0, 82.0, 0.1, 0.1),
    }
    interim = tmp_path / "interim"
    interim.mkdir()
    with rasterio.open(interim / "vnl_russia_2024.tif", "w", **profile) as dst:
        dst.write(data, 1)
    out, img = build_lightmap(2024, dest_dir=tmp_path / "out", interim_dir=interim)
    assert img.shape == (4, 6) and img[0, 0] > 200
    meta = json.loads((tmp_path / "out" / "lightmap_2024.meta.json").read_text(encoding="utf-8"))
    assert abs(meta["bounds"]["east"] - 25.0) < 1e-6 and abs(meta["bounds"]["south"] - 78.0) < 1e-6
    with rasterio.open(out) as src:
        assert src.read(1).shape == (4, 6)
