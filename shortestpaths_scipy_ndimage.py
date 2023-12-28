from datetime import datetime as dt
import numpy as np
import os
import geopandas as gpd
import rasterio as rio
from skimage.graph import route_through_array
from shapely.geometry import LineString, MultiLineString


def shortestpaths(output_gpkg, presence_thinned, cost, year_field, start_year, end_year):
    # Initialize an empty list to store features
    features = []
    # Read cost raster as array and mask NoData values
    cost_array = cost.read(1, masked=True)
    
    # Iterate through the specified range of years.
    # start_year + 1 because no paths can be created in the first year.
    # end_year + 1 because range end is not included in range.
    for year in range(start_year + 1, end_year + 1):
        print(f"[{dt.now().strftime('%H:%M:%S')}] Calculating least-cost paths for year {year}...")

        # Create GeoSeries with points for the current year
        year_source_points = presence_thinned[presence_thinned[year_field] == year]['geometry']
    
        # Loop through each source point
        for source_point in year_source_points:
            # Create GeoSeries with points from previous years
            earlier_dest_points = presence_thinned[presence_thinned[year_field] < year]['geometry']
    
            # Convert points to cost raster coordinates
            source_coords = rio.transform.rowcol(cost.transform, source_point.x, source_point.y)
            dest_coords = [(rio.transform.rowcol(cost.transform, dest_point.x, dest_point.y)) for dest_point in earlier_dest_points]

            # Use route_through_array for least-cost path calculation and allow diagonal steps
            path = [route_through_array(cost_array, source_coords, dest, fully_connected=True) for dest in dest_coords]
    
            # Store the paths and associated information in the features list
            for i, dest_point in enumerate(earlier_dest_points):
                path_coords, acc_cost = path[i]
                line_strings = [LineString([cost.xy(coord[0], coord[1]) for coord in path_coords])]
                line_geometry = MultiLineString(line_strings)

                # Store the line_geometry and any other relevant attributes in a dictionary
                feature = {
                    'geometry': line_geometry,
                    'properties': {
                        'year_source': year,
                        # 'year_destination': presence_thinned.iloc[i][year_field],  # this fetches wrong year information, fix later
                        'accumulated_cost': acc_cost
                    }
                }
    
                # Append the feature to the list
                features.append(feature)
    
    # Create a GeoDataFrame from the list of features and set CRS
    result_gdf = gpd.GeoDataFrame.from_features(features)
    result_gdf.set_crs(cost.crs, inplace=True)
    
    # Save the GeoDataFrame to a GeoPackage
    if os.path.exists(output_gpkg):
        result_gdf.to_file(output_gpkg, layer=f"{presence_name}_{run}_paths", driver='GPKG', append="layer")
    else:
        result_gdf.to_file(output_gpkg, layer=f"{presence_name}_{run}_paths", driver='GPKG')

    print(f"[{dt.now().strftime('%H:%M:%S')}] Least-cost paths saved to '{presence_name}_{run}.gpkg', layer '{presence_name}_{run}_paths'.")
