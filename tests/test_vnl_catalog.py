from citiesneversleep.sources.vnl_zenodo import VNL_FILENAME_RE


def test_vnl_filename_regex():
    name = "nightlights.average_viirs.v21_m_500m_s_20130101_20131231_go_epsg4326_v20250904.tif"
    m = VNL_FILENAME_RE.search(name)
    assert m is not None
    assert int(m.group(1)) == 2013


def test_vnl_filename_rejects_dmsp():
    name = "nightlights.average_dmsp.v10_m_1km_s_19920101_20241231_go_epsg4326_v20251006.tif"
    assert VNL_FILENAME_RE.search(name) is None
