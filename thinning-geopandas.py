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

fishnet.set_crs(epsg=crs, inplace=True)

# Perform a spatial join between points and fishnet using 'intersects' relationship
# sys:1: FutureWarning: The `op` parameter is deprecated and will be removed in a future release. Please use the `predicate` parameter instead.
print(f"[{datetime.now().strftime('%H:%M:%S')}] Joining occurrences and fishnet cells...")
result = gpd.sjoin(points, fishnet, how="inner", op="intersects")

# Get the point with the minimum observation_year for each fishnet cell
# result = result.sort_values("observation_year").groupby("index_right").first()

# Group by fishnet cell and find the point with the minimum observation_year in each group
print(f"[{datetime.now().strftime('%H:%M:%S')}] Grouping by fishnet cell...")
result = result.groupby("index_right").apply(lambda group: group.loc[group['observation_year'].idxmin()])

# Reset the index
result.reset_index(drop=True, inplace=True)

# Save the result GeoDataFrame to the geodatabase
# result.to_file(fr"FileGDB:{path_gdb}?layer=msculpturalis_occurrence_20230925_thinned", driver="FileGDB")
result.to_file("points_thinned.gpkg", layer="points_thinned", driver="GPKG")

# Convert the GeoPackage file to a feature class in the geodatabase using arcpy
arcpy.conversion.ExportFeatures(f"points_thinned.gpkg\points_thinned", fr"{path_gdb}\msculpturalis_occurrence_20230925_thinned")

# Optionally, remove the GeoPackage file if no longer needed
os.remove("points_thinned.gpkg")