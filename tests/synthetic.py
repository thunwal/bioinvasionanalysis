"""
Invented observations for the smoke tests: two introductions (near Lyon in 2010 and near Vienna in 2014) that spread
outwards by about 50 km per year. They only exercise the code; they are not biological data.
"""
import numpy as np
import pandas as pd
import rasterio as rio
from pyproj import Transformer

REPO_DEMO_SURFACE = "data/cost_surface_gtopo30_esri102031_5km_exp_base1_k9.tif"
INTRODUCTIONS = [("France", 4.8, 45.7, 2010), ("Austria", 16.4, 48.2, 2014)]  # location, lon, lat, first year
LAST_YEAR = 2024


def write_observations(cost_path, csv_path, per_introduction=400, speed_m=50_000, seed=1):
    rng = np.random.default_rng(seed)
    with rio.open(cost_path) as r:
        values = r.read(1, masked=True)
        rows, cols = np.nonzero(~np.ma.getmaskarray(values))
        xs, ys = rio.transform.xy(r.transform, rows, cols)
        to_raster = Transformer.from_crs("EPSG:4326", r.crs, always_xy=True)
        to_wgs84 = Transformer.from_crs(r.crs, "EPSG:4326", always_xy=True)
    xs, ys = np.asarray(xs), np.asarray(ys)
    records = []
    for location, lon, lat, first_year in INTRODUCTIONS:
        ox, oy = to_raster.transform(lon, lat)
        distance = np.hypot(xs - ox, ys - oy)
        years = first_year + np.floor(distance / speed_m).astype(int)
        candidates = np.flatnonzero(years <= LAST_YEAR)
        chosen = rng.choice(candidates, size=per_introduction, replace=False)
        jitter = rng.integers(0, 2, size=per_introduction)
        lons, lats = to_wgs84.transform(xs[chosen], ys[chosen])
        for x, y, year in zip(lons, lats, np.minimum(years[chosen] + jitter, LAST_YEAR)):
            records.append({"longitude": round(float(x), 5), "latitude": round(float(y), 5), "year": int(year),
                            "location": location})
    pd.DataFrame(records).to_csv(csv_path, index=False)
    return csv_path
