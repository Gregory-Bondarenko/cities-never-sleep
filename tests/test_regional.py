import numpy as np
import pandas as pd

from citiesneversleep.metrics.regional import fit_regional_mode, regional_adjustment
from citiesneversleep.metrics.trends import log_trend

YEARS = list(range(2012, 2025))


def _synthetic(seed: int = 0):
    """Города на сетке: свой тренд, шум и общий региональный узор.

    Узор: запад против востока; амплитуды по годам в сумме дают ноль.
    """
    rng = np.random.default_rng(seed)
    lat, lon = np.meshgrid(np.linspace(45, 65, 12), np.linspace(30, 130, 15))
    lat, lon = lat.ravel(), lon.ravel()
    n = len(lat)
    ids = [f"Q{i}" for i in range(n)]
    pattern = np.tanh((80 - lon) / 20)  # +1 на западе, -1 на востоке
    amp = np.array([0.0, 0.1, -0.15, 0.05, 0.0, -0.05, 0.15, -0.1, 0.0, 0.3, -0.3, 0.05, -0.05])
    trend = rng.normal(0, 0.03, n)
    years = np.array(YEARS)
    log = (
        trend[:, None] * (years - years[0])[None]
        + np.cumsum(amp)[None] * pattern[:, None]
        + rng.normal(0, 0.02, (n, len(years)))
    )
    lights = pd.DataFrame(
        {
            "city_id": np.repeat(ids, len(years)),
            "year": np.tile(years, n),
            "rel": np.exp(log).ravel(),
        }
    )
    coords = pd.DataFrame({"lat": lat, "lon": lon}, index=ids)
    return lights, coords, trend, pattern, amp


def test_mode_recovers_pattern_and_amplitude():
    lights, coords, _, pattern, amp = _synthetic()
    wide = lights.pivot(index="city_id", columns="year", values="rel")
    mode, pat = fit_regional_mode(np.log(wide), coords)
    r = np.corrcoef(pat.reindex(coords.index), pattern)[0, 1]
    sign = np.sign(r)
    assert abs(r) > 0.95
    assert np.corrcoef(sign * mode.amplitude, amp[1:])[0, 1] > 0.95
    assert mode.explained > 0.5


def test_adjustment_reduces_noise_and_keeps_trend():
    lights, coords, trend, _, _ = _synthetic(1)
    factor, _ = regional_adjustment(lights, "rel", coords)
    adj = lights.assign(adj=lights["rel"] * factor.to_numpy())
    before, after = [], []
    for i, (_, g) in enumerate(adj.groupby("city_id", sort=False)):
        before.append(log_trend(g["year"], g["rel"]).slope - trend[i])
        after.append(log_trend(g["year"], g["adj"]).slope - trend[i])
    assert np.mean(np.abs(after)) < np.mean(np.abs(before))
    wide = adj.pivot(index="city_id", columns="year", values="adj")
    resid = np.diff(np.log(wide.to_numpy()), axis=1)
    wide0 = adj.pivot(index="city_id", columns="year", values="rel")
    resid0 = np.diff(np.log(wide0.to_numpy()), axis=1)
    assert resid.var() < 0.5 * resid0.var()


def test_city_outside_sample_gets_interpolated_factor():
    lights, coords, _, _, _ = _synthetic(2)
    lights.loc[(lights["city_id"] == "Q0") & (lights["year"] == 2015), "rel"] = 0.0
    factor, _ = regional_adjustment(lights, "rel", coords)
    q0 = factor[lights["city_id"] == "Q0"]
    assert q0.notna().all() and (q0 != 1.0).any()
