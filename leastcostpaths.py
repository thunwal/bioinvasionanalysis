from datetime import datetime as dt
import numpy as np
import os
import geopandas as gpd
import rasterio as rio
from skimage.graph import MCP_Geometric
from shapely.geometry import LineString, MultiLineString


def paths(out_gpkg, out_lyr_paths, presence_thinned, cost, year_field, start_year, end_year):
    # Initialize an empty list to store features
    features = []
    # Read cost raster as array
    cost_array = cost.read(1, masked=True)
    # Identify NoData cells
    nodata_mask = np.ma.getmask(cost_array)
    # Set NoData cells to infinite
    cost_array[nodata_mask] = np.inf

    # Iterate through the specified range of years.
    # start_year + 1 because no paths can be created in the first year.
    # end_year + 1 because range end is not included in range.
    for year in range(start_year + 1, end_year + 1):
        print(f"[{dt.now().strftime('%H:%M:%S')}] Calculating least-cost paths for year {year}...")

        # Select known points from previous years
        known_points = presence_thinned[presence_thinned[year_field] < year]['geometry']
        known_coords = np.array(
            [(rio.transform.rowcol(cost.transform, known_point.x, known_point.y)) for known_point in known_points])

        # Select new points from current year
        new_points = presence_thinned[presence_thinned[year_field] == year]['geometry']
        new_coords = np.array(
            [(rio.transform.rowcol(cost.transform, new_point.x, new_point.y)) for new_point in new_points])
        new_coords_n = new_coords.shape[0]

        # Calculate accumulated costs to reach known points
        mcp = MCP_Geometric(cost_array)
        acc_cost_array, traceback_array = mcp.find_costs(starts=known_coords, ends=new_coords, find_all_ends=True)

        # Find least-cost path for each new point
        for i in range(new_coords_n):
            try:
                # Find least-cost path to any known point
                path = mcp.traceback(new_coords[i, :])

                # Get the associated cost by selecting the accumulated cost value at the path end (= new point)
                row_index, col_index = path[-1]
                acc_cost = acc_cost_array[row_index][col_index]

                # Create path geometry
                line_strings = [LineString([cost.xy(coord[0], coord[1]) for coord in path])]
                line_geometry = MultiLineString(line_strings)

                # Create feature with path geometry and attributes
                feature = {
                    'geometry': line_geometry,
                    'properties': {
                        'year_new_point': year,
                        'accumulated_cost': acc_cost
                    }
                }

                # Append the feature to the features list
                features.append(feature)

            except ValueError:
                print(f"[{dt.now().strftime('%H:%M:%S')}] INFO: No path found for a point.")
    
    # Create a GeoDataFrame from the list of features and set CRS
    result_gdf = gpd.GeoDataFrame.from_features(features)
    result_gdf.set_crs(cost.crs, inplace=True)
    
    # Save the GeoDataFrame to a GeoPackage
    if os.path.exists(out_gpkg):
        result_gdf.to_file(out_gpkg, layer=out_lyr_paths, driver="GPKG", append="layer")
    else:
        result_gdf.to_file(out_gpkg, layer=out_lyr_paths, driver="GPKG")

    print(f"[{dt.now().strftime('%H:%M:%S')}] Least-cost paths saved to {out_gpkg}, layer {out_lyr_paths}.")
