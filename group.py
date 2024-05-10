from datetime import datetime as dt
import os
import numpy as np
import pandas as pd
import geopandas as gpd
from shapely.geometry import MultiLineString, LineString, Point
import math


def get_endpoints(geom):
    """
    Extracts the start and end point of a LineString or MultiLineString.
    """
    if isinstance(geom, LineString):
        return [geom.coords[0], geom.coords[-1]]
    elif isinstance(geom, MultiLineString):
        return [line.coords[0] for line in geom.geoms] + [line.coords[-1] for line in geom.geoms]


def assign_group_ids(lines):
    """
    Assigns an ID to each group of MultiLineStrings which share start and/or end points.
    """
    # Work with dataframe copy to avoid warning from GeoPandas
    gdf = lines.copy()

    # Adds start and endpoint to the dataframe
    gdf['endpoints'] = gdf.geometry.apply(get_endpoints)

    # Initialize column for storing the group ID
    gdf['group_id'] = None

    # Iteratively check each feature's connectivity and tag it with group ID
    group_id = 0

    while gdf['group_id'].isnull().any():
        # Start with the first untagged feature
        untagged = gdf[gdf['group_id'].isnull()]
        first_untagged_idx = untagged.index[0]
        current_endpoints = set(untagged.at[first_untagged_idx, 'endpoints'])

        connected = {first_untagged_idx}
        more_to_check = True

        while more_to_check:
            more_to_check = False
            for idx, row in untagged.iterrows():
                if idx not in connected:
                    # Check if any endpoint matches
                    if any(pt in current_endpoints for pt in row['endpoints']):
                        connected.add(idx)
                        current_endpoints.update(row['endpoints'])
                        more_to_check = True

        # Assign the group ID to all connected features
        gdf.loc[list(connected), 'group_id'] = group_id
        group_id += 1

    # Cleanup before returning
    gdf = gdf.drop(columns=['endpoints'])

    return gdf


def upper_outlier_fence(in_gpkg, in_paths):
    """
    Returns the upper outlier fence (Q3 + 1.5 x IQR) for accumulated cost as a quantile and an absolute value.
    """
    gdf = gpd.read_file(in_gpkg, layer=in_paths)

    # Calculate Q1 and Q3
    q1 = np.quantile(gdf['accumulated_cost'], 0.25)
    q3 = np.quantile(gdf['accumulated_cost'], 0.75)

    # Define the upper outlier fence
    iqr = q3 - q1
    upper_bound = q3 + 1.5 * iqr

    # Find rank of the outlier fence
    upper_bound_quantile = (gdf['accumulated_cost'] < upper_bound).mean()

    print(f"[{dt.now().strftime('%H:%M:%S')}] Upper outlier fence (Q3 + 1.5 x IQR) for accumulated cost is {upper_bound} ({upper_bound_quantile} quantile).")

    return upper_bound_quantile, upper_bound


def sensitivity_analysis(in_gpkg, in_paths, out_csv_outlier_test, quantile_range):
    """
    Runs sensitivity analysis over a range of upper outlier fences to determine the impact on the number of resulting groups.
    """
    gdf = gpd.read_file(in_gpkg, layer=in_paths)

    print(f"[{dt.now().strftime('%H:%M:%S')}] Testing upper outlier fences from {quantile_range[0]} quantile to {quantile_range[-1]} quantile...")

    results = []

    for quantile in quantile_range:
        # Copy the GeoDataFrame to avoid modifying the original
        gdf_copy = gdf.copy()

        # Apply quantile threshold to filter paths
        threshold = np.quantile(gdf_copy['accumulated_cost'], quantile)
        gdf_filtered = gdf_copy[gdf_copy['accumulated_cost'] < threshold]

        # Assign subpopulation IDs to the filtered DataFrame
        gdf_filtered = assign_group_ids(gdf_filtered)

        # Count distinct subpopulation IDs
        num_groups = gdf_filtered['group_id'].nunique()

        # Record the results
        results.append({'quantile': quantile, 'num_groups': num_groups})

    pd.DataFrame(results).to_csv(out_csv_outlier_test, index=False)
    print(f"[{dt.now().strftime('%H:%M:%S')}] Test results saved to {out_csv_outlier_test}.")


def group_paths(in_out_gpkg, in_paths, out_paths, quantile):
    """
    Assigns paths to groups of connected paths. This is done by ignoring outlier paths with a cost higher than
    the input quantile parameter and checking the connectivity of the remaining paths.
    """
    paths = gpd.read_file(in_out_gpkg, layer=in_paths)

    threshold = np.quantile(paths['accumulated_cost'], quantile)
    paths_filtered = paths[paths['accumulated_cost'] < threshold]
    print(f"[{dt.now().strftime('%H:%M:%S')}] Paths with a cost < {threshold} ({quantile} quantile) loaded.")

    print(f"[{dt.now().strftime('%H:%M:%S')}] Grouping least-cost paths by their connectivity...")
    paths_filtered_grouped = assign_group_ids(paths_filtered)

    # Save the selected and tagged paths to the GeoPackage which specific to the script run
    paths_filtered_grouped.to_file(in_out_gpkg, layer=out_paths)
    print(f"[{dt.now().strftime('%H:%M:%S')}] Grouped paths saved to {in_out_gpkg}, layer {out_paths}.")


def group_points(in_out_gpkg, in_points, in_paths, out_points, cell_size):
    """
    Assigns presence points to groups using a spatial join (nearest).
    Coordinate matching is not possible here because the path endpoints are centered on cost raster cells.
    """
    gdf_points = gpd.read_file(in_out_gpkg, layer=in_points)
    gdf_points['point_id'] = gdf_points.index
    gdf_paths = gpd.read_file(in_out_gpkg, layer=in_paths)
    half_diagonal = (math.sqrt(2) * cell_size) / 2

    # Extract endpoints of all paths and create a dataframe
    print(f"[{dt.now().strftime('%H:%M:%S')}] Assigning presence points to the groups formed by paths...")
    endpoints = []

    for index, path in gdf_paths.iterrows():
        points = get_endpoints(path.geometry)
        for point in points:
            # Append endpoint geometry and group_id to the list
            endpoints.append({'geometry': Point(point), 'group_id': path.group_id})

    gdf_endpoints = gpd.GeoDataFrame(endpoints, crs=gdf_paths.crs)

    # Spatial join: assigns each point the group_id of the nearest endpoint
    gdf_points = gpd.sjoin_nearest(gdf_points, gdf_endpoints[['geometry', 'group_id']], how='left', max_distance=half_diagonal, distance_col='dist')
    # Drop duplicated points (duplication occurs when more than one path has an endpoint in the same cell)
    gdf_points.drop_duplicates(subset=['point_id'], keep='first', inplace=True)
    gdf_points.drop(columns=['index_right', 'point_id'], inplace=True)

    # Save the selected and tagged paths to the GeoPackage which specific to the script run
    gdf_points.to_file(in_out_gpkg, layer=out_points)
    print(f"[{dt.now().strftime('%H:%M:%S')}] Grouped points saved to {in_out_gpkg}, layer {out_points}.")
