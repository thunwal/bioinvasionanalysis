from datetime import datetime as dt
import numpy as np
import os
import geopandas as gpd
import rasterio as rio
from skimage.graph import MCP_Geometric
from shapely.geometry import LineString, MultiLineString


# def calculate_least_cost_paths(source_coords, dest_coords, cost_array):
#     path = []
#     for dest in dest_coords:
#         try:
#             p = route_through_array(cost_array, source_coords, dest, fully_connected=True)
#             path.append(p)
#         except ValueError:
#             continue
#     return path


def calculate_least_cost_paths(mcp, source_coords, dest_coords):
    try:
        costs, traceback_array = mcp.find_costs(starts=source_coords, ends=dest_coords, find_all_ends=True)
        return costs, traceback_array
    except ValueError:
        print(f"[{dt.now().strftime('%H:%M:%S')}] INFO: No path found for source point {source_coords}.")
        return None, None

def shortestpaths(out_gpkg, out_lyr_paths, presence_thinned, cost, year_field, start_year, end_year):
    # Initialize an empty list to store features
    features = []
    # Read cost raster as array
    cost_array = cost.read(1, masked=True)
    # Identify NoData cells
    nodata_mask = np.ma.getmask(cost_array)
    # Set NoData cells to np.inf
    cost_array[nodata_mask] = np.inf

    # Iterate through the specified range of years.
    # start_year + 1 because no paths can be created in the first year.
    # end_year + 1 because range end is not included in range.
    for year in range(start_year + 1, end_year + 1):
        print(f"[{dt.now().strftime('%H:%M:%S')}] Calculating least-cost paths for year {year}...")

        # create graph
        mcp = MCP_Geometric(cost_array)

        # Create GeoSeries with points for the current year
        year_source_points = presence_thinned[presence_thinned[year_field] == year]['geometry']
    
        # Loop through each source point
        for source_point in year_source_points:
            # Create GeoSeries with points from previous years
            earlier_dest_points = presence_thinned[presence_thinned[year_field] < year]['geometry']
    
            # Convert points to cost raster coordinates
            source_coords = [rio.transform.rowcol(cost.transform, source_point.x, source_point.y)]
            dest_coords = [(rio.transform.rowcol(cost.transform, dest_point.x, dest_point.y)) for dest_point in earlier_dest_points]

            # source_coords = [source_coords]

            # Use MCP_Geometric for least-cost path calculation
            costs, traceback_array = calculate_least_cost_paths(mcp, source_coords, dest_coords)

            # Find the minimum cost and corresponding path
            min_cost = np.min(costs)
            min_cost_index = np.argmin(costs)
            # min_cost_path = MCP_Geometric.traceback(traceback_array, [min_cost_index])  # causes access violation
            min_cost_path = mcp.traceback([min_cost_index])

            # Store the path and associated information in the features list
            line_strings = [LineString([cost.xy(coord[0], coord[1]) for coord in min_cost_path])]
            line_geometry = MultiLineString(line_strings)

            # Store the line_geometry and any other relevant attributes in a dictionary
            feature = {
                'geometry': line_geometry,
                'properties': {
                    'year_source': year,
                    'accumulated_cost': min_cost
                }
            }

            # Use route_through_array for least-cost path calculation and allow diagonal steps
            # tbd: input all destination points at once (do not iterate) and use correct functions
            # path = calculate_least_cost_paths(source_coords, dest_coords, cost_array)

            # # Store the paths and associated information in the features list
            # for i, dest_point in enumerate(earlier_dest_points):
            #     path_coords, acc_cost = path[i]
            #     line_strings = [LineString([cost.xy(coord[0], coord[1]) for coord in path_coords])]
            #     line_geometry = MultiLineString(line_strings)
            #
            #     # Store the line_geometry and any other relevant attributes in a dictionary
            #     feature = {
            #         'geometry': line_geometry,
            #         'properties': {
            #             'year_source': year,
            #             'accumulated_cost': acc_cost
            #         }
            #     }
    
            # Append the feature to the list
            features.append(feature)
    
    # Create a GeoDataFrame from the list of features and set CRS
    result_gdf = gpd.GeoDataFrame.from_features(features)
    result_gdf.set_crs(cost.crs, inplace=True)
    
    # Save the GeoDataFrame to a GeoPackage
    if os.path.exists(out_gpkg):
        result_gdf.to_file(out_gpkg, layer=out_lyr_paths, driver="GPKG", append="layer")
    else:
        result_gdf.to_file(out_gpkg, layer=out_lyr_paths, driver="GPKG")

    print(f"[{dt.now().strftime('%H:%M:%S')}] Least-cost paths saved to {out_gpkg}, layer {out_lyr_paths}.")
