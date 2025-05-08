from datetime import datetime as dt
import numpy as np
import geopandas as gpd
import rasterio as rio
from skimage.graph import MCP_Geometric
from shapely.geometry import LineString, MultiLineString


def paths(out_gpkg, out_paths, in_points, in_cost, year_field, start_year, end_year):
    """
    Creates least-cost paths that connect each observation to the nearest earlier observation based on the least cost.
    """
    # Initialize an empty list to store features
    features = []
    # Read the first band of the cost raster
    cost_array = in_cost.read(1, masked=True)
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
        known_points = in_points[in_points[year_field] < year]['geometry']
        known_coords = np.array(
            [(rio.transform.rowcol(in_cost.transform, known_point.x, known_point.y)) for known_point in known_points])

        # Select new points from current year
        new_points = in_points[in_points[year_field] == year]['geometry']
        new_coords = np.array(
            [(rio.transform.rowcol(in_cost.transform, new_point.x, new_point.y)) for new_point in new_points])
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
                line_strings = [LineString([in_cost.xy(coord[0], coord[1]) for coord in path])]
                line_geometry = MultiLineString(line_strings)

                # Create feature with path geometry and attributes
                # tbd: find a way to add the year of the source point
                feature = {
                    'geometry': line_geometry,
                    'properties': {
                        'destination_year': year,
                        'accumulated_cost': acc_cost
                    }
                }

                # Append the feature to the features list
                features.append(feature)

            except ValueError:
                print(f"[{dt.now().strftime('%H:%M:%S')}] INFO: No path found for a point.")
    
    # Create a GeoDataFrame from the list of features and set CRS
    result_gdf = gpd.GeoDataFrame.from_features(features)
    result_gdf.set_crs(in_cost.crs, inplace=True)
    
    # Save the GeoDataFrame to a GeoPackage
    result_gdf.to_file(out_gpkg, layer=out_paths)
    print(f"[{dt.now().strftime('%H:%M:%S')}] Least-cost paths saved to '{out_gpkg}', layer '{out_paths}'.")

    # Return dataframe
    return result_gdf
