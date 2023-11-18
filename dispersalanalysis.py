import arcpy
from datetime import datetime as dt
import geopandas as gpd
import numpy as np
import os
from shapely.geometry import Polygon

# Input parameters
# Set "run" to name your model run. All outputs will be named {presence}_{run}_{featureclass}.
# Any existing files and layers with the same name will be overwritten.
start_year = 2008  # year of first observation, or first year of analysis
end_year = 2023  # year of latest observation, or last year of analysis
gdb = r"C:\Daten\Dokumente\UNIGIS\ArcGIS Projekte\p_distanzanalyse\p_distanzanalyse.gdb"
presence = "msculpturalis_20230925"
cost = "msculpturalis_sdm_clip_rev"  # "costs_with_barriers", "msculpturalis_sdm_clip", "msculpturalis_sdm_clip_rev"
run = "sdmrev"  # "costrast1", "sdm", "sdmrev"
workdir = os.path.dirname(gdb)

# Read the raster properties using ArcPy
print(f"[{dt.now().strftime('%H:%M:%S')}] Reading raster properties...")
desc = arcpy.Describe(os.path.join(gdb, cost))
extent = desc.extent
cell_size = desc.meanCellWidth
xmin, ymin, xmax, ymax = map(int, [extent.XMin, extent.YMin, extent.XMax, extent.YMax])
crs_code = desc.spatialReference.factoryCode
print(f"[{dt.now().strftime('%H:%M:%S')}] Raster has CRS factoryCode {crs_code} and cell size {cell_size}.")

# ArcPy environment settings
arcpy.env.snapRaster = os.path.join(gdb, cost)
arcpy.env.parallelProcessingFactor = "100%"
arcpy.env.overwriteOutput = True
arcpy.env.addOutputsToMap = False
arcpy.env.autoCancelling = True
arcpy.env.outputCoordinateSystem = desc.spatialReference


def thinning():
    # Read presence data
    print(f"[{dt.now().strftime('%H:%M:%S')}] Reading presence data...")
    points = gpd.read_file(gdb, driver="FileGDB", layer=presence)
    
    # Reproject points to match the coordinate system of the raster
    # Problem: We don't know the CRS authority. Try EPSG and ESRI.
    try:
        # Attempt to project with "epsg:{crs_code}"
        points = points.to_crs(f"epsg:{crs_code}")
        crs_string = f"epsg:{crs_code}"
        print(f"[{dt.now().strftime('%H:%M:%S')}] Projected presence data to {crs_string}.")
    except Exception as e:
        print(f"[{dt.now().strftime('%H:%M:%S')}] Projection with 'epsg:{crs_code}' not possible: {e}")
        try:
            # Attempt to project with "esri:{crs_code}"
            points = points.to_crs(f"esri:{crs_code}")
            crs_string = f"esri:{crs_code}"
            print(f"[{dt.now().strftime('%H:%M:%S')}] Projected presence data to {crs_string}.")
        except Exception as e2:
            print(f"[{dt.now().strftime('%H:%M:%S')}] Projection with 'esri:{crs_code}' not possible: {e2}")
            # Raise an exception if both attempts fail
            raise Exception(f"[{dt.now().strftime('%H:%M:%S')}] Failed to project presence data with 'epsg:{crs_code}' and 'esri:{crs_code}'.") from e2

    # Create a temporary fishnet based on the raster properties
    print(f"[{dt.now().strftime('%H:%M:%S')}] Creating temporary fishnet with raster properties...")
    x_range = np.arange(xmin, xmax, cell_size)
    y_range = np.arange(ymin, ymax, cell_size)
    
    fishnet = gpd.GeoDataFrame(geometry=[Polygon([
        (x, y), (x + cell_size, y), (x + cell_size, y + cell_size), (x, y + cell_size)
    ]) for x in x_range for y in y_range])
    
    fishnet.set_crs(crs_string, inplace=True)
    
    # Join points with fishnet cells
    print(f"[{dt.now().strftime('%H:%M:%S')}] Joining presence data and fishnet polygons...")
    thinned = gpd.sjoin(points, fishnet, how="inner", predicate="intersects")
    
    # Group points by fishnet cell and select the point with the minimum observation_year in each group
    print(f"[{dt.now().strftime('%H:%M:%S')}] Selecting presence locations with minimum observation_year per cell...")
    thinned = thinned.groupby("index_right").apply(lambda group: group.loc[group['observation_year'].idxmin()])
    
    # Drop index and reset CRS (CRS information gets lost during sjoin or groupby)
    thinned.reset_index(drop=True, inplace=True)
    thinned.set_crs(crs_string, inplace=True)
    
    # Save the thinned points to the working directory
    # Target format is GeoPackage (*.gpkg) because GeoPandas cannot write to File GeoDatabase (*.gdb).
    thinned.to_file(os.path.join(workdir, f"{presence}_{run}_thinned.gpkg"), layer=f"{presence}_{run}_thinned", driver="GPKG")

    # Convert the GeoPackage file to a feature class in the File GeoDatabase using ArcPy.
    # Delete the target feature class if it exists.
    if arcpy.Exists(os.path.join(gdb, f"{presence}_{run}_thinned")):
        arcpy.Delete_management(os.path.join(gdb, f"{presence}_{run}_thinned"))

    arcpy.CopyFeatures_management(os.path.join(workdir, f"{presence}_{run}_thinned.gpkg", f"{presence}_{run}_thinned"),
                                  os.path.join(gdb, f"{presence}_{run}_thinned"))

    # Remove the GeoPackage file
    os.remove(os.path.join(workdir, f"{presence}_{run}_thinned.gpkg"))


def distacc():
    # Check out any necessary licenses.
    try:
        arcpy.CheckOutExtension("spatial")

        # Iterate through the specified range of years.
        # end_year is not included in range which fits our needs.
        for year in range(start_year, end_year, 1):

            # Form the output raster paths.
            path_dist_acc_raster = os.path.join(gdb, f"{presence}_{run}_{year}_acc")
            path_back_dir_raster = os.path.join(gdb, f"{presence}_{run}_{year}_back")

            # Select occurrences known in the respective year.
            arcpy.management.MakeFeatureLayer(os.path.join(gdb, f"{presence}_{run}_thinned"), "temp_layer", f"observation_year <= {year}")

            # Create distance accumulation raster.
            # Note: This function returns the raster which needs to be saved in an extra step.
            print(f"[{dt.now().strftime('%H:%M:%S')}] Creating distance accumulation raster for year {year}...")
            dist_acc_raster = arcpy.sa.DistanceAccumulation("temp_layer", "", "",
                                                            os.path.join(gdb, cost), "", "BINARY 1 -30 30", "", "BINARY 1 45",
                                                            path_back_dir_raster, "", "", "", "",
                                                            "", "", "GEODESIC")
            dist_acc_raster.save(path_dist_acc_raster)
            arcpy.Delete_management("temp_layer")

    finally:
        arcpy.CheckInExtension("spatial")


def optpaths():
    # Check out any necessary licenses.
    try:
        arcpy.CheckOutExtension("spatial")

        # Iterate through the specified range of years.
        # start_year + 1 because no paths can be created in the first year.
        # end_year + 1 because range end is not included in range.
        for idx, year in enumerate(range(start_year + 1, end_year + 1)):

            # Form the input raster paths based on the year. Subtract 1 year because we
            # want to create least-cost paths to occurrences known in the previous year.
            path_dist_acc_raster = os.path.join(gdb, f"{presence}_{run}_{year - 1}_acc")
            path_back_dir_raster = os.path.join(gdb, f"{presence}_{run}_{year - 1}_back")

            # Select occurrences with the respective observation year.
            arcpy.management.MakeFeatureLayer(os.path.join(gdb, f"{presence}_{run}_thinned"), "temp_layer", f"observation_year = {year}")

            # Create optimal paths.
            print(f"[{dt.now().strftime('%H:%M:%S')}] Calculating optimal paths for year {year}...")
            path_optpaths = fr"memory\optpaths"
            arcpy.sa.OptimalPathAsLine("temp_layer", path_dist_acc_raster, path_back_dir_raster, path_optpaths,
                                       "observation_year", "EACH_CELL", False)

            # Create new feature class in first iteration and append in subsequent iterations.
            if idx == 0:
                print(f"[{dt.now().strftime('%H:%M:%S')}] Saving optimal paths for year {year}...")
                arcpy.management.CopyFeatures(path_optpaths, os.path.join(gdb, f"{presence}_{run}_paths"))
            else:
                print(f"[{dt.now().strftime('%H:%M:%S')}] Appending optimal paths for year {year}...")
                arcpy.management.Append(inputs=[path_optpaths], target=os.path.join(gdb, f"{presence}_{run}_paths"))

            arcpy.Delete_management("temp_layer")
            arcpy.Delete_management(path_optpaths)

    finally:
        arcpy.CheckInExtension("spatial")


thinning()
distacc()
optpaths()
