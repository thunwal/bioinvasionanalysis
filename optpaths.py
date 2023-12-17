import arcpy
from datetime import datetime as dt
import os

def optpaths(gdb, presence, run, year_field, start_year, end_year):
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
