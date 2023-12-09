import arcpy
from datetime import datetime as dt
import geopandas as gpd
import numpy as np
import os
from shapely.geometry import Polygon

# PARAMETERS ------------------------------------------------------------------
gdb = r"C:\Daten\Dokumente\UNIGIS\ArcGIS Projekte\p_distanzanalyse\p_distanzanalyse.gdb"
workdir = os.path.dirname(gdb)
presence = "msculpturalis_20230925"  # input presence point data
cost = "msculpturalis_sdm_clip_rev_scaled100"  # input cost raster     msculpturalis_sdm_clip_rev     _rescaled100
run = "sdmrev100"  # output names will be prefixed {presence}_{run} and existing files/layers overwritten.      sdmrev  costrast1   simple100
year_field = "observation_year"  # field in presence data containing observation year
start_year = 2008  # year of first observation, or first year of analysis
end_year = 2023  # year of latest observation, or last year of analysis  # tbd: input = output does not work
# -----------------------------------------------------------------------------

# Read raster properties. Using ArcPy to support File GeoDatabase.
print(f"[{dt.now().strftime('%H:%M:%S')}] Reading raster properties...")
desc = arcpy.Describe(os.path.join(gdb, cost))
extent = desc.extent
cell_size = desc.meanCellWidth
cell_size_y = desc.meanCellHeight
xmin, ymin, xmax, ymax = map(int, [extent.XMin, extent.YMin, extent.XMax, extent.YMax])
crs_code = desc.spatialReference.factoryCode
print(f"[{dt.now().strftime('%H:%M:%S')}] Raster has CRS factoryCode {crs_code} and cell size {cell_size} x {cell_size_y}.")

# Check if cell size width and height are the same. If not, stop script execution.
# The thinning process relies on a fishnet with equal cell side length.
if cell_size != cell_size_y:
    raise Exception("Raster cells are required to have equal side lengths for the thinning procedure.")

# ArcPy environment settings
arcpy.env.snapRaster = os.path.join(gdb, cost)
arcpy.env.parallelProcessingFactor = "100%"
arcpy.env.overwriteOutput = True
arcpy.env.addOutputsToMap = False
arcpy.env.autoCancelling = True
arcpy.env.outputCoordinateSystem = desc.spatialReference


def thinning():
    # Read presence data. Import the column specified in year_field only.
    # Set year_field to int32 (Long) as the default Int64 (Big) is not supported by OptimalPathAsLine,
    # and int16 (Short) is not supported by GeoPandas to_file().
    print(f"[{dt.now().strftime('%H:%M:%S')}] Reading presence data...")
    points = gpd.read_file(gdb, driver="FileGDB", layer=presence, include_fields=[year_field])
    points[year_field] = points[year_field].astype("int32")

    # Reproject points to match the coordinate system of the raster.
    # We only know the CRS code, but not the CRS authority -> try EPSG and ESRI.
    # tbd: alternative approach: EPSG code range is 1024 to 32767.
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
    
    # Group points by fishnet cell and select the point with the minimum year in each group
    print(f"[{dt.now().strftime('%H:%M:%S')}] Selecting presence locations with minimum year per cell...")
    thinned = thinned.groupby("index_right").apply(lambda group: group.loc[group[year_field].idxmin()])
    
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
            arcpy.management.MakeFeatureLayer(os.path.join(gdb, f"{presence}_{run}_thinned"), "temp_layer", f"{year_field} <= {year}")

            # Create distance accumulation raster.
            # Note: This function returns the raster which needs to be saved in an extra step.
            print(f"[{dt.now().strftime('%H:%M:%S')}] Creating distance accumulation raster for year {year}...")
            dist_acc_raster = arcpy.sa.DistanceAccumulation("temp_layer", "", "",
                                                            os.path.join(gdb, cost), "", "", "", "",
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
            arcpy.management.MakeFeatureLayer(os.path.join(gdb, f"{presence}_{run}_thinned"), "temp_layer", f"{year_field} = {year}")

            # Create optimal paths.
            print(f"[{dt.now().strftime('%H:%M:%S')}] Calculating optimal paths for year {year}...")
            path_optpaths = fr"memory\optpaths"
            arcpy.sa.OptimalPathAsLine("temp_layer", path_dist_acc_raster, path_back_dir_raster, path_optpaths,
                                       year_field, "EACH_CELL", False)

            # Create new feature class in first iteration and append in subsequent iterations.
            if idx == 0:
                print(f"[{dt.now().strftime('%H:%M:%S')}] Saving optimal paths for year {year}...")
                arcpy.management.CopyFeatures(path_optpaths, os.path.join(gdb, f"{presence}_{run}_paths"))
            else:
                print(f"[{dt.now().strftime('%H:%M:%S')}] Appending optimal paths for year {year}...")
                arcpy.management.Append(inputs=[path_optpaths], target=os.path.join(gdb, f"{presence}_{run}_paths"))

            arcpy.Delete_management("temp_layer")
            arcpy.Delete_management(path_optpaths)

        # The observation year of a presence point has been saved in "DestID", rename to "year".
        arcpy.management.AlterField(os.path.join(gdb, f"{presence}_{run}_paths"), "DestID", "year")
        print(f"[{dt.now().strftime('%H:%M:%S')}] Done! Renamed 'DestID' to 'year' in the target feature class.")

    finally:
        arcpy.CheckInExtension("spatial")


thinning()
distacc()
optpaths()
