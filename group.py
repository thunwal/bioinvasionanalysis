from datetime import datetime as dt
import numpy as np
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
