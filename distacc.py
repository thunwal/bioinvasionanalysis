import arcpy
from datetime import datetime as dt
import os

def distacc(presence_thinned, cost, run, year_field, start_year, end_year):
    # Iterate through the specified range of years.
    # Note: end_year is not included in range, which fits our needs.
    for year in range(start_year, end_year, 1):

        # Form the output raster paths.
        path_dist_acc_raster = os.path.join(gdb, f"{presence}_{run}_{year}_acc")
        path_back_dir_raster = os.path.join(gdb, f"{presence}_{run}_{year}_back")

        # Select occurrences known in the respective year.
        arcpy.management.MakeFeatureLayer(os.path.join(gdb, f"{presence}_{run}_thinned"), "temp_layer", f"{year_field} <= {year}")

        # Run distance accumulation
        print(f"[{dt.now().strftime('%H:%M:%S')}] Creating cost accumulation and back direction rasters for year {year}...")
        dist_acc_raster = arcpy.sa.DistanceAccumulation("temp_layer", "", "",
                                                        os.path.join(gdb, cost), "", "", "", "",
                                                        path_back_dir_raster, "", "", "", "",
                                                        "", "", "GEODESIC")
        # Save cost accumulation raster (back direction raster is already saved by the DistanceAccumulation tool)
        # tbd: Raster name is not set, make sure the name is set correctly
        dist_acc_raster.setProperty("name", f"{presence}_{run}_{year}_acc")
        dist_acc_raster.save(path_dist_acc_raster)
        # delete the temp layer to ensure everything is cleaned up
        arcpy.Delete_management("temp_layer")
