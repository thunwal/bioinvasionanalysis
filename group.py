from datetime import datetime as dt
import os
import numpy as np
import pandas as pd
import geopandas as gpd
from shapely.geometry import MultiLineString, LineString


def get_endpoints(geom):
    """
    Extracts the start and end point of a LineString or MultiLineString.
    """
    if isinstance(geom, LineString):
        return [geom.coords[0], geom.coords[-1]]
    elif isinstance(geom, MultiLineString):
        return [line.coords[0] for line in geom.geoms] + [line.coords[-1] for line in geom.geoms]


def assign_group_ids(gdf_original):
    """
    Assigns an ID to each group of MultiLineStrings which share start and/or end points.
    """
    # Work with dataframe copy to avoid warning from Pandas
    gdf = gdf_original.copy()

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
        new_connections = True

        while new_connections:
            new_connections = False
            for idx, row in untagged.iterrows():
                if idx not in connected:
                    # Check if any endpoint matches
                    if any(pt in current_endpoints for pt in row['endpoints']):
                        connected.add(idx)
                        current_endpoints.update(row['endpoints'])
                        new_connections = True

        # Assign the group ID to all connected features
        gdf.loc[list(connected), 'group_id'] = group_id
        group_id += 1

    # Cleanup before returning
    gdf = gdf.drop(columns=['endpoints'])

    return gdf


import geopandas as gpd


def calculate_iqr_threshold(gpkg, lyr_paths):
    # Load the layer from the GeoPackage
    gdf = gpd.read_file(gpkg, layer=lyr_paths)

    # Calculate Q1 and Q3
    q1 = gdf['accumulated_cost'].quantile(0.25)
    q3 = gdf['accumulated_cost'].quantile(0.75)
    iqr = q3 - q1

    # Define the upper bound using 1.5 * IQR
    upper_bound = q3 + 1.5 * iqr

    # Find the quantile of the upper bound
    proportion_below_upper_bound = (gdf['accumulated_cost'] < upper_bound).mean()
    #quantile_of_upper_bound = gdf['accumulated_cost'].quantile(upper_bound / gdf['accumulated_cost'].max())

    print(f"[{dt.now().strftime('%H:%M:%S')}] Threshold for outlier removal: quantile {proportion_below_upper_bound}, cost {upper_bound}.")

    return proportion_below_upper_bound, upper_bound


def sensitivity_analysis(workdir_path, gpkg, lyr_paths, quantile_range):
    """
    Runs sensitivity analysis over a range of quantiles to determine the impact on subpopulation identification.

    :param gdf: GeoDataFrame containing the paths and their costs.
    :param quantile_range: Iterable of quantiles to test.
    :return: DataFrame with quantiles and corresponding number of subpopulations.
    """
    gdf = gpd.read_file(gpkg, layer=lyr_paths, driver="GPKG")
    results = []

    for quantile in quantile_range:
        print(f"[{dt.now().strftime('%H:%M:%S')}] Testing the {quantile} quantile...")

        # Copy the GeoDataFrame to avoid modifying the original
        gdf_copy = gdf.copy()

        # Apply quantile threshold to filter paths
        threshold = np.quantile(gdf_copy['accumulated_cost'], quantile)
        gdf_filtered = gdf_copy[gdf_copy['accumulated_cost'] <= threshold]

        # Assign subpopulation IDs to the filtered DataFrame
        gdf_filtered = assign_group_ids(gdf_filtered)

        # Count distinct subpopulation IDs
        num_groups = gdf_filtered['group_id'].nunique()

        # Record the results
        results.append({'quantile': quantile, 'num_groups': num_groups})

    pd.DataFrame(results).to_csv(os.path.join(workdir_path, 'sensitivity_analysis_results.csv'), index=False)

    return pd.DataFrame(results)


def group_paths(gpkg, lyr_paths, lyr_paths_grouped, quantile):
    paths = gpd.read_file(gpkg, layer=lyr_paths, driver="GPKG")
    threshold = np.quantile(paths['accumulated_cost'], quantile)
    paths_filtered = paths[paths['accumulated_cost'] < threshold]
    print(f"[{dt.now().strftime('%H:%M:%S')}] Paths with a cost lower than {threshold} ({quantile} quantile) loaded.")

    print(f"[{dt.now().strftime('%H:%M:%S')}] Grouping connected least-cost paths...")
    paths_filtered_grouped = assign_group_ids(paths_filtered)

    # Save the selected and tagged paths to the GeoPackage which specific to the script run
    paths_filtered_grouped.to_file(gpkg, layer=lyr_paths_grouped, driver="GPKG")
    print(f"[{dt.now().strftime('%H:%M:%S')}] Grouped least-cost paths saved to {gpkg}, layer {lyr_paths_grouped}.")
