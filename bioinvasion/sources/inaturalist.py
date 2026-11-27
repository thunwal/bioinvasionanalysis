"""
Downloads observations from iNaturalist (https://www.inaturalist.org) in the standard presence schema
(see bioinvasion/sources/files.py).
"""
import json
import time
import urllib.parse
import urllib.request
from datetime import datetime as dt

import geopandas as gpd
import numpy as np
import pandas as pd
from shapely.geometry import box

from bioinvasion.naturalearth import natural_earth

API = "https://api.inaturalist.org"
HEADERS = {"User-Agent": "bioinvasionanalysis (https://github.com/thunwal/bioinvasionanalysis)"}
PAGE_SIZE = 200  # maximum allowed by the API
REQUEST_INTERVAL = 1.0  # seconds; iNaturalist asks API users to stay at or below ~1 request per second


def _log(msg):
    print(f"[{dt.now().strftime('%H:%M:%S')}] {msg}")


def _get(path, params):
    url = f"{API}{path}?{urllib.parse.urlencode(params)}"
    request = urllib.request.Request(url, headers=HEADERS)
    for attempt in range(6):
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                return json.load(response)
        except Exception as e:
            wait = 5 * 2 ** attempt
            _log(f"Request failed ({e}), retrying in {wait} s...")
            time.sleep(wait)
    raise RuntimeError(f"iNaturalist API request failed repeatedly: {url}")


def resolve_taxon(taxon):
    """Returns (taxon_id, scientific name) for a taxon ID or a scientific name."""
    if isinstance(taxon, (int, np.integer)) or str(taxon).isdigit():
        result = _get(f"/v1/taxa/{int(taxon)}", {})["results"][0]
    else:
        results = _get("/v1/taxa", {"q": taxon, "per_page": 30})["results"]
        exact = [t for t in results if t["name"].lower() == str(taxon).lower()]
        if not exact:
            suggestions = ", ".join(t["name"] for t in results[:5])
            raise ValueError(f"No iNaturalist taxon named '{taxon}'. Did you mean: {suggestions}?")
        result = exact[0]
    return result["id"], result["name"]


def raster_bbox_4326(raster):
    """Lon/lat bounding box of an open rasterio dataset (edges densified, so curved edges are covered)."""
    b = raster.bounds
    edge = gpd.GeoSeries([box(b.left, b.bottom, b.right, b.top).segmentize(
        max(b.right - b.left, b.top - b.bottom) / 100)], crs=raster.crs).to_crs(4326)
    return tuple(edge.total_bounds)


def fetch_inaturalist(taxon, bbox_4326, research_grade_only=True, include_obscured=False,
                      max_positional_accuracy=None, start_year=None, end_year=None, max_observations=None,
                      log=_log, progress=None):
    """
    Downloads all observations of 'taxon' (scientific name or iNaturalist taxon ID) within 'bbox_4326'
    (xmin, ymin, xmax, ymax) and returns them in the standard presence schema, plus a list of report lines.

    research_grade_only: only observations with quality grade "research" (community-confirmed identification)
    include_obscured: keep observations whose coordinates were randomised by iNaturalist (by up to ~20 km)
                      for privacy or species protection reasons
    max_positional_accuracy: drops observations whose positional accuracy (in m) is worse than this value;
                             observations without accuracy information are kept. None = no limit.
    max_observations: abort if the query returns more observations (protects the public web app)
    """
    taxon_id, taxon_name = resolve_taxon(taxon)
    xmin, ymin, xmax, ymax = bbox_4326
    quality_grade = "research" if research_grade_only else "research,needs_id,casual"
    query = {"taxon_id": taxon_id, "quality_grade": quality_grade,
             "swlng": xmin, "swlat": ymin, "nelng": xmax, "nelat": ymax,
             "per_page": PAGE_SIZE, "order_by": "id", "order": "asc",
             "fields": "id,observed_on,location,obscured,positional_accuracy"}
    if start_year is not None:
        query["d1"] = f"{start_year}-01-01"
    if end_year is not None:
        query["d2"] = f"{end_year}-12-31"

    total = _get("/v2/observations", {**query, "per_page": 0})["total_results"]
    if max_observations is not None and total > max_observations:
        raise ValueError(f"The query returns {total} observations, more than the limit of {max_observations}. "
                         f"Use a smaller cost surface or download the data yourself and upload it as CSV.")
    log(f"Downloading {total} observations of {taxon_name} (iNaturalist taxon {taxon_id}, quality grade "
        f"'{quality_grade}'). This takes about {max(1, round(total / PAGE_SIZE * 2.5 / 60))} min...")

    rows, id_above = [], 0
    while True:
        started = time.time()
        results = _get("/v2/observations", {**query, "id_above": id_above})["results"]
        if not results:
            break
        rows += results
        id_above = results[-1]["id"]
        if progress:
            progress(len(rows), total)
        time.sleep(max(0.0, REQUEST_INTERVAL - (time.time() - started)))

    df = pd.DataFrame(rows, columns=["id", "observed_on", "location", "obscured", "positional_accuracy"])
    report = [f"Source: iNaturalist, taxon {taxon_name} (ID {taxon_id}), downloaded {dt.now():%Y-%m-%d %H:%M}",
              f"Query: quality grade '{quality_grade}', bounding box {', '.join(f'{v:.4f}' for v in bbox_4326)} "
              f"(lon/lat), years {start_year or 'all'}-{end_year or 'all'}",
              f"Observations downloaded: {len(df)}"]
    n = len(df)
    df = df.dropna(subset=["location", "observed_on"])
    df["year"] = pd.to_datetime(df["observed_on"], errors="coerce").dt.year
    df = df.dropna(subset=["year"])
    report.append(f"Removed without date or location: {n - len(df)}")
    if not include_obscured:
        n = len(df)
        df = df[~df["obscured"].fillna(False).astype(bool)]
        report.append(f"Removed with obscured coordinates: {n - len(df)}")
    if max_positional_accuracy is not None:
        n = len(df)
        df = df[~(df["positional_accuracy"] > max_positional_accuracy)]
        report.append(f"Removed with positional accuracy worse than {max_positional_accuracy:g} m: {n - len(df)} "
                      f"(observations without accuracy information are kept)")

    lat_lon = df["location"].str.split(",", expand=True).astype(float)
    gdf = gpd.GeoDataFrame(
        {"year": df["year"].astype("int32").to_numpy(), "location": "",
         "source": "iNaturalist", "source_id": df["id"].astype(str).to_numpy()},
        geometry=gpd.points_from_xy(lat_lon[1], lat_lon[0]), crs=4326)
    if len(gdf):
        gdf["location"] = assign_countries(gdf)
    report.append(f"Observations imported: {len(gdf)}; 'location' = Natural Earth country (nearest within 20 km for "
                  f"points just off the coast, otherwise 'unknown')")
    return gdf, report


def assign_countries(points, max_distance_m=20000):
    """
    Country name (Natural Earth) for each point. Points just outside the coastline polygons are assigned
    the nearest country within 'max_distance_m'; all others get 'unknown'.
    """
    xmin, ymin, xmax, ymax = points.total_bounds
    countries = natural_earth("countries", (xmin - 1, ymin - 1, xmax + 1, ymax + 1), columns=["NAME_EN"])
    joined = gpd.sjoin(points[["geometry"]], countries, how="left", predicate="within")
    country = joined[~joined.index.duplicated()]["NAME_EN"]

    missing = country.isna()
    if missing.any():
        crs = points.estimate_utm_crs()
        near = gpd.sjoin_nearest(points.loc[missing, ["geometry"]].to_crs(crs), countries.to_crs(crs), how="left",
                                 max_distance=max_distance_m)
        country.loc[missing] = near[~near.index.duplicated()]["NAME_EN"]
    return country.fillna("unknown").to_numpy()
