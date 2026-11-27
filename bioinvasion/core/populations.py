import math
import numpy as np
import pandas as pd
import geopandas as gpd
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import connected_components
from shapely.geometry import MultiLineString, LineString, Point


def get_endpoints(geom):
    """Start and end point(s) of a LineString or MultiLineString."""
    if isinstance(geom, LineString):
        return [geom.coords[0], geom.coords[-1]]
    elif isinstance(geom, MultiLineString):
        return [line.coords[0] for line in geom.geoms] + [line.coords[-1] for line in geom.geoms]


def group_paths(paths):
    """
    Assigns a population id ('group_id') to paths that are connected by shared endpoints, directly or via other paths.

    The paths and their endpoints form a network: a path links its endpoints, and two paths are connected if they
    share an endpoint (identical coordinates). The populations are the separate parts of this network ("connected
    components"), found by scipy in one pass. The ids are numbered in the order of the first path of each population.
    """
    gdf = paths.copy()
    node_ids = {}
    path_index, node_index = [], []
    for i, geom in enumerate(gdf.geometry):
        for point in get_endpoints(geom):
            path_index.append(i)
            node_index.append(node_ids.setdefault(point, len(node_ids)))
    n = len(gdf) + len(node_ids)
    links = coo_matrix((np.ones(len(path_index)), (path_index, np.array(node_index) + len(gdf))), shape=(n, n))
    _, component = connected_components(links, directed=False)
    gdf["group_id"] = pd.Series(pd.factorize(component[:len(gdf)])[0], index=gdf.index).astype(str).astype("string")
    return gdf


def filter_paths(paths, threshold):
    """Removes paths with an accumulated cost at or above the threshold. Returns the kept paths and their share."""
    kept = paths[paths["accumulated_cost"] < threshold].reset_index(drop=True)
    return kept, len(kept) / len(paths) if len(paths) else float("nan")


def group_points(points, paths_grouped, cell_size):
    """
    Assigns each observation the population of the nearest path endpoint within half a cell diagonal, i.e. of a path
    starting or ending in (or, if there is none, next to) the observation's cell. Path endpoints are cell centres.
    Observations without such an endpoint get no group_id (isolated).
    """
    points = points.copy()
    points["point_id"] = np.arange(len(points))
    endpoints = [{"geometry": Point(p), "group_id": gid}
                 for geom, gid in zip(paths_grouped.geometry, paths_grouped["group_id"]) for p in get_endpoints(geom)]
    gdf_endpoints = gpd.GeoDataFrame(endpoints, columns=["geometry", "group_id"], crs=paths_grouped.crs)
    gdf_endpoints["group_id"] = gdf_endpoints["group_id"].astype("string")
    out = gpd.sjoin_nearest(points, gdf_endpoints[["geometry", "group_id"]], how="left",
                            max_distance=math.sqrt(2) * cell_size / 2, distance_col="dist")
    # Several endpoints in the same cell belong to the same population: keep one match per observation
    out = out.drop_duplicates(subset=["point_id"], keep="first")
    return out.drop(columns=["index_right", "point_id"])


def delineate(paths, points, threshold, cell_size):
    """Population delineation: threshold the paths, group them, and assign the observations to the groups."""
    kept, share = filter_paths(paths, threshold)
    paths_grouped = group_paths(kept)
    return paths_grouped, group_points(points, paths_grouped, cell_size), share
