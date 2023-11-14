import geopandas as gpd
from shapely.geometry import Point, Polygon
import arcpy
import numpy as np
from datetime import datetime

# Set paths
path_gdb = r"C:\Daten\Dokumente\UNIGIS\ArcGIS Projekte\p_distanzanalyse\p_distanzanalyse.gdb"
path_occurrences = fr"{path_gdb}\msculpturalis_occurrence_20230925"
path_cost_surface = fr"{path_gdb}\costs_with_barriers"

# Read the raster extent using arcpy
print(f"[{datetime.now().strftime('%H:%M:%S')}] Reading raster data...")
desc = arcpy.Describe(path_cost_surface)
extent = desc.extent
cell_size = desc.meanCellWidth
xmin, ymin, xmax, ymax = map(int, [extent.XMin, extent.YMin, extent.XMax, extent.YMax])
crs = desc.spatialReference.factoryCode

# Read points from the geodatabase
print(f"[{datetime.now().strftime('%H:%M:%S')}] Reading occurrence data...")
points = gpd.read_file(path_gdb, driver='FileGDB', layer='msculpturalis_occurrence_20230925')

# Reproject points to match the coordinate system of the raster
print(f"[{datetime.now().strftime('%H:%M:%S')}] Projecting occurrence data to EPSG:{crs}...")
points = points.to_crs(epsg=crs)

# Create a fishnet based on the raster extent
print(f"[{datetime.now().strftime('%H:%M:%S')}] Creating fishnet...")
x_range = np.arange(xmin, xmax, cell_size)
y_range = np.arange(ymin, ymax, cell_size)

fishnet = gpd.GeoDataFrame(geometry=[Polygon([
    (x, y), (x + cell_size, y), (x + cell_size, y + cell_size), (x, y + cell_size)
]) for x in x_range for y in y_range])

# Create an empty GeoDataFrame for the result
result = gpd.GeoDataFrame(columns=points.columns)

# Iterate over fishnet cells
print(f"[{datetime.now().strftime('%H:%M:%S')}] Selecting earliest occurrence per fishnet cell...")
for index, row in fishnet.iterrows():
    cell_geometry = row['geometry']

    # Select points that intersect with the current fishnet cell
    selected_points = points[
        points.intersects(cell_geometry) & ~points['geometry'].isna() & ~points['observation_year'].isna()]

    # If there are points in the cell, find the one with the minimum observation_year
    if not selected_points.empty:
        min_observation_point = selected_points.loc[selected_points['observation_year'].idxmin()]

        # Append the selected point to the result GeoDataFrame
        result = result.append(min_observation_point, ignore_index=True)

# Save the result GeoDataFrame to the geodatabase
result.to_file(fr"FileGDB:{path_gdb}?layer=msculpturalis_occurrence_20230925_thinned", driver="FileGDB")