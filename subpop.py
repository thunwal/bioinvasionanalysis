from datetime import datetime as dt
import numpy as np
import geopandas as gpd


def assign_subpopulation_ids(gdf):
    # Reset the index of the DataFrame to ensure consistent integer-location based indexing
    gdf = gdf.reset_index(drop=True)
    gdf['subpop_id'] = None
    subpop_id = 0

    spatial_index = gdf.sindex

    while gdf['subpop_id'].isnull().any():
        # Find the first untagged feature
        first_untagged_idx = gdf[gdf['subpop_id'].isnull()].index[0]
        to_check = [first_untagged_idx]
        connected_indices = set([first_untagged_idx])

        while to_check:
            current_idx = to_check.pop(0)
            current_geom = gdf.at[current_idx, 'geometry']

            # Potential matches based on spatial index
            possible_matches_index = list(spatial_index.intersection(current_geom.bounds))
            for n_idx in possible_matches_index:
                if n_idx in connected_indices:
                    continue
                other_geom = gdf.at[n_idx, 'geometry']
                if other_geom.touches(current_geom) or other_geom == current_geom:
                    connected_indices.add(n_idx)
                    to_check.append(n_idx)

        # Assign the subpopulation ID to all connected features
        for idx in connected_indices:
            gdf.at[idx, 'subpop_id'] = subpop_id

        subpop_id += 1

    return gdf


def subpop(gpkg, lyr_paths, lyr_paths_tagged, quantile):
    paths = gpd.read_file(gpkg, layer=lyr_paths, driver="GPKG")
    threshold = np.quantile(paths['accumulated_cost'], quantile)
    paths_filtered = paths[paths['accumulated_cost'] < threshold]

    print(f"[{dt.now().strftime('%H:%M:%S')}] Merging paths with a cost lower than {threshold} ({quantile} quantile)...")
    # tbd: herausfinden, woher die einzelnen, zusätzlichen und einzeln getaggten Segmente herkommen
    paths_filtered_tagged = assign_subpopulation_ids(paths_filtered)

    # Save the selected and tagged paths to the GeoPackage which specific to the script run
    paths_filtered_tagged.to_file(gpkg, layer=lyr_paths_tagged, driver="GPKG")
    print(f"[{dt.now().strftime('%H:%M:%S')}] Merged paths saved to '{gpkg}', layer '{lyr_paths_tagged}'.")
