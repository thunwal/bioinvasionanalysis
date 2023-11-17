import arcpy
from datetime import datetime as dt
import geopandas as gpd
import numpy as np
# import os
from shapely.geometry import Polygon

# Set paths
path = r"C:\Daten\Dokumente\UNIGIS\ArcGIS Projekte\p_distanzanalyse"
path_gdb = fr"{path}\p_distanzanalyse.gdb"
path_occurrences = fr"{path_gdb}\msculpturalis_occurrence_20230925"
path_cost_surface = fr"{path_gdb}\costs_with_barriers"

# Read the raster properties using ArcPy
print(f"[{dt.now().strftime('%H:%M:%S')}] Reading raster properties...")
desc = arcpy.Describe(path_cost_surface)
extent = desc.extent
cell_size = desc.meanCellWidth
xmin, ymin, xmax, ymax = map(int, [extent.XMin, extent.YMin, extent.XMax, extent.YMax])
crs = desc.spatialReference.factoryCode

# ArcPy environment settings
arcpy.env.snapRaster = path_cost_surface
arcpy.env.parallelProcessingFactor = "100%"
arcpy.env.overwriteOutput = True
arcpy.env.addOutputsToMap = False
arcpy.env.autoCancelling = True
arcpy.env.scratchWorkspace = path_gdb
arcpy.env.workspace = path_gdb
arcpy.env.outputCoordinateSystem = desc.spatialReference

# Read occurrences
print(f"[{dt.now().strftime('%H:%M:%S')}] Reading occurrence data...")
points = gpd.read_file(path_gdb, driver='FileGDB', layer='msculpturalis_occurrence_20230925')

# Reproject points to match the coordinate system of the raster
print(f"[{dt.now().strftime('%H:%M:%S')}] Projecting occurrence data to EPSG:{crs}...")
points = points.to_crs(epsg=crs)

# Create a temporary fishnet based on the raster properties
print(f"[{dt.now().strftime('%H:%M:%S')}] Creating temporary fishnet with raster properties...")
x_range = np.arange(xmin, xmax, cell_size)
y_range = np.arange(ymin, ymax, cell_size)

fishnet = gpd.GeoDataFrame(geometry=[Polygon([
    (x, y), (x + cell_size, y), (x + cell_size, y + cell_size), (x, y + cell_size)
]) for x in x_range for y in y_range])

fishnet.set_crs(epsg=crs, inplace=True)

# Join points with fishnet cells
print(f"[{dt.now().strftime('%H:%M:%S')}] Joining occurrences and fishnet cells...")
thinned = gpd.sjoin(points, fishnet, how="inner", predicate="intersects")

# Group points by fishnet cell and select the point with the minimum observation_year in each group
print(f"[{dt.now().strftime('%H:%M:%S')}] Selecting occurrences with minimum observation_year per cell...")
thinned = thinned.groupby("index_right").apply(lambda group: group.loc[group['observation_year'].idxmin()])

# Drop index and reset CRS (CRS information gets lost during sjoin or groupby)
thinned.reset_index(drop=True, inplace=True)
thinned.set_crs(epsg=crs, inplace=True)

# Save the thinned points to the working directory
# Target format is GeoPackage (*.gpkg) because GeoPandas cannot write to File GeoDatabase (*.gdb).
thinned.to_file(fr"{path}\points_thinned.gpkg", layer="points_thinned", driver="GPKG")
print(f"[{dt.now().strftime('%H:%M:%S')}] Done! Thinned occurrences saved in {path}\points_thinned.gpkg.")

# Convert the GeoPackage file to a feature class in the geodatabase using arcpy
# arcpy.conversion.ExportFeatures(fr"{path}\points_thinned.gpkg\points_thinned", fr"{path_occurrences}_thinned")

# Remove the GeoPackage file if no longer needed
# os.remove("points_thinned.gpkg")