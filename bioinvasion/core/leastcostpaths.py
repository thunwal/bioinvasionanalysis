import numpy as np
import geopandas as gpd
from rasterio.transform import rowcol
from skimage.graph import MCP_Geometric
from shapely.geometry import LineString, MultiLineString


def least_cost_paths(points, cost, start_year, end_year, progress=None, log=print):
    """
    Connects each observation to the nearest earlier observation (in terms of accumulated cost) by a least-cost path,
    in annual steps. 'points' are the thinned observations in the CRS of the cost surface, 'cost' an open rasterio
    dataset. 'progress(done, total)' is called after each year, e.g. for a progress bar.
    Returns a GeoDataFrame with one path per reachable observation: destination_year, accumulated_cost, geometry.
    """
    features = []
    cost_array = cost.read(1, masked=True)
    cost_array[np.ma.getmask(cost_array)] = np.inf  # NoData cells cannot be crossed

    def cells(geoms):
        return np.array([rowcol(cost.transform, p.x, p.y) for p in geoms])

    years = range(start_year + 1, end_year + 1)  # no paths can lead to the first year
    for i, year in enumerate(years):
        log(f"Calculating least-cost paths for year {year}...")
        known = cells(points[points["year"] < year].geometry)
        new = cells(points[points["year"] == year].geometry)

        mcp = MCP_Geometric(cost_array)
        acc_cost_array, _ = mcp.find_costs(starts=known, ends=new, find_all_ends=True)
        for cell in new:
            try:
                path = mcp.traceback(cell)
            except ValueError:
                log(f"INFO: No path found for an observation of {year}.")
                continue
            row, col = path[-1]
            features.append({
                "geometry": MultiLineString([LineString([cost.xy(r, c) for r, c in path])]),
                "properties": {"destination_year": year, "accumulated_cost": acc_cost_array[row][col]},
            })
        if progress:
            progress(i + 1, len(years))

    return gpd.GeoDataFrame.from_features(features, crs=cost.crs)
