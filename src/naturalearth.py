"""
Access to Natural Earth vector data (https://www.naturalearthdata.com, public domain).
Layers are downloaded once and cached locally.
"""
import os
import urllib.request
from datetime import datetime as dt

import geopandas as gpd
from shapely.geometry import box

CACHE_DIR = os.path.join(os.path.expanduser("~"), ".cache", "bioinvasionanalysis")

LAYERS = {
    "ocean": "https://naciscdn.org/naturalearth/10m/physical/ne_10m_ocean.zip",
    "lakes": "https://naciscdn.org/naturalearth/10m/physical/ne_10m_lakes.zip",
    "borders": "https://naciscdn.org/naturalearth/10m/cultural/ne_10m_admin_0_boundary_lines_land.zip",
    "countries": "https://naciscdn.org/naturalearth/10m/cultural/ne_10m_admin_0_countries.zip",
}


def natural_earth(layer, bbox_4326=None, crs=None, cache_dir=CACHE_DIR, columns=None):
    """
    Returns a Natural Earth layer, optionally clipped to a lon/lat bounding box (xmin, ymin, xmax, ymax)
    and projected to 'crs'.
    """
    os.makedirs(cache_dir, exist_ok=True)
    url = LAYERS[layer]
    local = os.path.join(cache_dir, os.path.basename(url))
    if not os.path.exists(local):
        print(f"[{dt.now().strftime('%H:%M:%S')}] Downloading Natural Earth layer '{layer}' to '{cache_dir}'...")
        urllib.request.urlretrieve(url, local)
    gdf = gpd.read_file(local, bbox=bbox_4326, columns=columns)
    if bbox_4326 is not None:
        gdf = gdf.clip(box(*bbox_4326))
    if crs is not None:
        gdf = gdf.to_crs(crs)
    return gdf
